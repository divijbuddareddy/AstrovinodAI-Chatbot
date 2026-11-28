"""Subscription plans: monthly chat limits, 3-year PhonePe AutoPay subscriptions, and payments.

Plans                 FREE 10 chats / STANDARD 150 / PREMIUM 300 / VIP unlimited, per month.
What counts as a chat Every question after the birth profile is set up (registration and the first report are free).
Billing               Monthly subscription with a 3-year PhonePe AutoPay mandate (renews every month for up to 3 years).

Tables (created and migrated automatically):
  subscriptions  one row per customer: current plan, billing cycle, AutoPay mandate state & expiry, chats used
  payments       every payment attempt (setup / renewal / one-time: created / paid / cancelled)
"""
import calendar
import logging
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Integer, MetaData, String, Table, insert, inspect, select, text, update

log = logging.getLogger("astrovinod")

MANDATE_YEARS = 3
NOTIFY_LEAD = timedelta(hours=30)
REDEEM_MIN_WAIT = timedelta(hours=24)
LINK_VALID = timedelta(hours=24)

PLANS = {
    "free":     {"name": "FREE",     "price": 0,    "chats": 10,   "icon": "🆓"},
    "standard": {"name": "STANDARD", "price": 299,  "chats": 150,  "icon": "⭐"},
    "premium":  {"name": "PREMIUM",  "price": 499,  "chats": 300,  "icon": "💎"},
    "vip":      {"name": "VIP",      "price": 4999, "chats": None, "icon": "👑"},  # None = unlimited
}
PAID = ("standard", "premium", "vip")
_LEGACY_PLANS = {"gold": "standard", "platinum": "premium"}
PLAN_IMAGE = "static/plans2.jpg"
PLAN_IMAGES = {
    "standard": "static/standard2.jpg",
    "premium":  "static/premium.jpg",
    "vip":      "static/vip.jpg",
}


def norm_plan(plan: str | None) -> str:
    p = (plan or "").strip().lower()
    p = _LEGACY_PLANS.get(p, p)
    return p if p in PLANS else "free"


def plan_info(plan: str | None) -> dict:
    return PLANS[norm_plan(plan)]

meta = MetaData()
subscriptions = Table(
    "subscriptions", meta,
    Column("phone_number", String(32), primary_key=True),
    Column("plan", String(16), nullable=False, server_default="free"),
    Column("period_start", String(40), nullable=False, server_default=""),
    Column("period_end", String(40), nullable=False, server_default=""),
    Column("chats_used", Integer, nullable=False, server_default="0"),
    Column("updated_at", String(40), nullable=False, server_default=""),
    Column("billing_mode", String(16), nullable=False, server_default="manual"),
    Column("merchant_subscription_id", String(64), nullable=False, server_default=""),
    Column("phonepe_subscription_id", String(64), nullable=False, server_default=""),
    Column("mandate_state", String(24), nullable=False, server_default=""),
    Column("mandate_expires_at", String(40), nullable=False, server_default=""),
    Column("next_billing_at", String(40), nullable=False, server_default=""),
    Column("notified_order_id", String(64), nullable=False, server_default=""),
    Column("notified_at", String(40), nullable=False, server_default=""),
)
payments = Table(
    "payments", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("token", String(64), nullable=False, unique=True, index=True),
    Column("phone_number", String(32), nullable=False, index=True),
    Column("plan", String(16), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("status", String(16), nullable=False, server_default="created"),  # created | paid | cancelled
    Column("gateway", String(16), nullable=False, server_default="dummy"),
    Column("gateway_ref", String(64), nullable=False, server_default=""),
    Column("created_at", String(40), nullable=False, server_default=""),
    Column("paid_at", String(40), nullable=False, server_default=""),
    Column("merchant_subscription_id", String(64), nullable=False, server_default=""),
    Column("payment_type", String(16), nullable=False, server_default="setup"),
)

_ready = False
_ready_lock = threading.Lock()
_renewal_lock = threading.Lock()


def _add_missing_columns(engine) -> None:
    insp = inspect(engine)
    for tbl in (subscriptions, payments):
        have = {c["name"] for c in insp.get_columns(tbl.name)}
        missing = [c for c in tbl.columns if c.name not in have]
        if not missing:
            continue
        with engine.begin() as conn:
            for col in missing:
                conn.execute(text(f"ALTER TABLE {tbl.name} ADD COLUMN {col.name} VARCHAR(64) NOT NULL DEFAULT ''"))
        log.info("Added %s column(s): %s", tbl.name, ", ".join(c.name for c in missing))


def _engine():
    global _ready
    from . import bot
    engine = bot.store().engine
    if not _ready:
        with _ready_lock:
            if not _ready:
                meta.create_all(engine)
                _add_missing_columns(engine)
                _ready = True
    return engine


def _add_months(dt: datetime, months: int = 1) -> datetime:
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, calendar.monthrange(y, m)[1])
    return dt.replace(year=y, month=m, day=d)


def _add_years(dt: datetime, years: int = MANDATE_YEARS) -> datetime:
    return _add_months(dt, years * 12)


def epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def mandate_expiry(start: datetime | None = None) -> datetime:
    return _add_years(start or _now(), MANDATE_YEARS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def _dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def public_url() -> str:
    return (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
            or "https://astrovinodai-chatbot.onrender.com").rstrip("/")


# ---------------------------------------------------------------- subscriptions
def get(phone: str) -> dict:
    """Current subscription; starts FREE, rolls over monthly (or back to FREE if a paid period ended without renewal)."""
    engine = _engine()
    now = _now()
    with engine.begin() as conn:
        row = conn.execute(select(subscriptions).where(subscriptions.c.phone_number == phone)).mappings().first()
        if not row:
            sub = {"phone_number": phone, "plan": "free", "period_start": _iso(now),
                   "period_end": _iso(_add_months(now, 1)), "chats_used": 0, "updated_at": _iso(now),
                   "billing_mode": "manual", "merchant_subscription_id": "", "phonepe_subscription_id": "",
                   "mandate_state": "", "mandate_expires_at": "", "next_billing_at": "",
                   "notified_order_id": "", "notified_at": ""}
            conn.execute(insert(subscriptions).values(**sub))
            return sub
        sub = dict(row)
        end = _dt(sub["period_end"])
        if not end or now >= end:
            exp = _dt(sub.get("mandate_expires_at", ""))
            m_state = sub.get("mandate_state", "")
            if m_state == "ACTIVE" and exp and now >= exp:
                m_state = "EXPIRED"
            sub.update(plan="free", period_start=_iso(now), period_end=_iso(_add_months(now, 1)), chats_used=0,
                       mandate_state=m_state, updated_at=_iso(now))
            conn.execute(update(subscriptions).where(subscriptions.c.phone_number == phone)
                         .values(plan="free", period_start=sub["period_start"], period_end=sub["period_end"],
                                 chats_used=0, mandate_state=m_state, updated_at=sub["updated_at"]))
        return sub


def remaining(sub: dict) -> int | None:
    limit = plan_info(sub.get("plan"))["chats"]
    return None if limit is None else max(0, limit - sub["chats_used"])


def _chat_status_note(plan_key: str, left: int | None) -> tuple[str, bool]:
    """Return (note, show_plans_image) for the remaining chats after counting one chat."""
    if left is None:
        return "", False
    name = PLANS[plan_key]["name"]
    if left == 0:
        return (f"ℹ️ That was the last chat of your *{name}* plan for this period.\n\n"
                "Choose a plan below to continue:"), True
    if plan_key == "free" and left == 5:
        return (f"ℹ️ You have *{left} free chats left* in your *{name}* plan for this period.\n\n"
                "Tap a plan below to upgrade anytime, or keep asking your remaining 5 questions:"), True
    if left <= 2:
        return f"ℹ️ {left} chat{'s' if left > 1 else ''} left in your *{name}* plan. Tap *PLANS* below to upgrade anytime.", False
    return "", False


def use_chat_status(phone: str) -> tuple[str, bool]:
    """Count one chat. Returns (message, show_plans_image)."""
    sub = get(phone)
    with _engine().begin() as conn:
        conn.execute(update(subscriptions).where(subscriptions.c.phone_number == phone)
                     .values(chats_used=subscriptions.c.chats_used + 1, updated_at=_iso(_now())))
    sub["chats_used"] += 1
    return _chat_status_note(norm_plan(sub.get("plan")), remaining(sub))


def use_chat(phone: str) -> str:
    """Count one chat. Returns a short note when the customer is running out ("" otherwise)."""
    msg, show_plans = use_chat_status(phone)
    if show_plans:
        return f"{msg}\n\n{plans_menu()}"
    return msg


def _date(iso: str) -> str:
    d = _dt(iso)
    return d.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y") if d else ""


def plan_buttons() -> list[tuple[str, str]]:
    return [(f"plan_{k}", "VIP" if k == "vip" else PLANS[k]["name"].title()) for k in PAID]


def plans_menu() -> str:
    lines = [f"{p['icon']} *{p['name']}* – {'Unlimited' if p['chats'] is None else p['chats']} chats/month – ₹{p['price']}"
             for k, p in PLANS.items() if k in PAID]
    return "\n".join(lines) + "\n\nReply *STANDARD*, *PREMIUM* or *VIP* to get your payment link."


def limit_prompt(customer: dict) -> tuple[str, str]:
    """When no chats remain: (image_caption_for_buttons, text_fallback). ("", "") if they may continue."""
    sub = get(customer["phone_number"])
    if remaining(sub) != 0:
        return "", ""
    first = (customer.get("full_name") or "").split(" ")[0]
    p = plan_info(sub.get("plan"))
    head = (f"🙏 {first + ' ji, y' if first else 'Y'}ou have used all *{p['chats']} chats* of your *{p['name']}* plan "
            "for this month.")
    renew = f"_Your {p['name']} chats renew on {_date(sub['period_end'])}._"
    caption = f"{head}\n\nTap a plan below to continue:\n\n{renew}"
    fallback = f"{head}\n\nTo continue your consultation, choose a plan:\n\n{plans_menu()}\n\n{renew}"
    return caption, fallback


def limit_message(customer: dict) -> str:
    """If the customer has no chats left, the message to send instead of an answer ("" if they may continue)."""
    return limit_prompt(customer)[1]


def status_prompt(phone: str) -> tuple[str, str]:
    sub = get(phone)
    p = plan_info(sub.get("plan"))
    left = remaining(sub)
    used = f"{sub['chats_used']} used, unlimited" if left is None else f"{sub['chats_used']} of {p['chats']} used, {left} left"
    if norm_plan(sub.get("plan")) == "free":
        until_line = f"📅 Renews: {_date(sub['period_end'])}"
    elif sub.get("mandate_state") == "ACTIVE":
        until_line = f"🔄 AutoPay: Active · next charge {_date(sub['period_end'])} (valid till {_date(sub.get('mandate_expires_at', ''))})"
    else:
        until_line = f"📅 Valid till: {_date(sub['period_end'])}"
    head = f"{p['icon']} Your plan: *{p['name']}*\n💬 Chats this month: {used}\n{until_line}"
    return f"{head}\n\nTap a plan below to upgrade:", f"{head}\n\nUpgrade options:\n\n{plans_menu()}"


def status_message(phone: str) -> str:
    return status_prompt(phone)[1]


# ---------------------------------------------------------------- WhatsApp commands
PLANS_CMD = re.compile(r"^\s*(plans?|view plans|upgrade|subscription|subscribe|recharge|my plan|balance|pricing|price list)\s*[.!?]*\s*$", re.I)
CHOOSE_CMD = re.compile(r"^\s*(?:buy\s+|get\s+|choose\s+)?(standard|premium|vip|gold|platinum)(?:\s+(?:plan|₹?\s*\d[\d,]*))?\s*[.!]*\s*$", re.I)


def payment_offer(phone: str, plan: str) -> dict:
    plan = norm_plan(plan)
    p = PLANS[plan]
    token = create_payment(phone, plan)
    url = f"{public_url()}/pay/{token}"
    chats = "Unlimited chats" if p["chats"] is None else f"{p['chats']} chats"
    body = (f"{p['icon']} *{p['name']} plan* – {chats}/month – *₹{p['price']}/month*\n\n"
            "Tap below to enable PhonePe AutoPay (3-year monthly subscription; cancel anytime in PhonePe).")
    fallback = (f"{p['icon']} *{p['name']} plan* – {chats}/month – *₹{p['price']}/month*\n\n"
                f"Tap the link to enable AutoPay & pay securely:\n{url}\n\n"
                "_Monthly AutoPay for 3 years. Valid for 24 hours. Your plan starts as soon as the payment is done._")
    return {"plan": plan, "price": p["price"], "url": url, "body": body,
            "button": f"Pay ₹{p['price']} Now", "footer": "Monthly AutoPay · 3-year mandate",
            "image_path": PLAN_IMAGES.get(plan, ""), "fallback": fallback}


def handle_command(customer: dict, text: str) -> dict | None:
    """Inspect PLANS / STANDARD / PREMIUM / VIP commands (never counted as chats)."""
    phone = customer["phone_number"]
    if PLANS_CMD.match(text or ""):
        body, fallback = status_prompt(phone)
        return {"kind": "plans", "body": body, "fallback": fallback}
    m = CHOOSE_CMD.match(text or "")
    if not m:
        return None
    return {"kind": "pay", **payment_offer(phone, m.group(1))}


def command_reply(customer: dict, text: str) -> str:
    """Replies to PLANS / STANDARD / PREMIUM / VIP (these never count as chats). "" if the text is not a command."""
    cmd = handle_command(customer, text)
    return cmd["fallback"] if cmd else ""


# ---------------------------------------------------------------- payments
def create_payment(phone: str, plan: str, payment_type: str = "setup") -> str:
    from . import phonepe
    plan = norm_plan(plan)
    token = secrets.token_urlsafe(16)
    with _engine().begin() as conn:
        conn.execute(insert(payments).values(token=token, phone_number=phone, plan=plan,
                                             amount=PLANS[plan]["price"], status="created",
                                             gateway="phonepe" if phonepe.enabled() else "dummy",
                                             gateway_ref="", paid_at="", merchant_subscription_id="",
                                             payment_type=payment_type, created_at=_iso(_now())))
    return token


def set_gateway_ref(token: str, ref: str, merchant_subscription_id: str = "") -> None:
    """Remember the gateway's order id (and subscription id) for a payment attempt before it is paid."""
    vals = {"gateway_ref": ref}
    if merchant_subscription_id:
        vals["merchant_subscription_id"] = merchant_subscription_id
    with _engine().begin() as conn:
        conn.execute(update(payments).where(payments.c.token == token, payments.c.status == "created").values(**vals))


def get_payment(token: str) -> dict | None:
    with _engine().connect() as conn:
        row = conn.execute(select(payments).where(payments.c.token == token)).mappings().first()
    return dict(row) if row else None


def link_expired(pay: dict) -> bool:
    created = _dt(pay["created_at"])
    return not created or _now() - created > LINK_VALID


def mark_paid(token: str, gateway_ref: str, phonepe_subscription_id: str = "",
              mandate_state: str = "", mandate_expires_at: str = "") -> dict | None:
    """Mark a payment paid and start the monthly cycle (with 3-year AutoPay mandate when applicable)."""
    now = _now()
    next_end = _add_months(now, 1)
    engine = _engine()
    with engine.begin() as conn:
        # "cancelled" too: someone may press Cancel on our page after actually paying in PhonePe.
        done = conn.execute(update(payments).where(payments.c.token == token,
                                                   payments.c.status.in_(("created", "cancelled")))
                            .values(status="paid", paid_at=_iso(now), gateway_ref=gateway_ref))
        if done.rowcount != 1:
            return None
        pay = dict(conn.execute(select(payments).where(payments.c.token == token)).mappings().first())
    get(pay["phone_number"])  # make sure the subscription row exists
    msid = pay.get("merchant_subscription_id") or (f"DUMMY-{pay['id']}" if pay["gateway"] == "dummy" else "")
    is_autopay = bool(msid)
    exp_iso = mandate_expires_at or (_iso(mandate_expiry(now)) if is_autopay else "")
    m_state = (mandate_state or "ACTIVE") if is_autopay else ""
    with engine.begin() as conn:
        conn.execute(update(subscriptions).where(subscriptions.c.phone_number == pay["phone_number"])
                     .values(plan=norm_plan(pay["plan"]), period_start=_iso(now), period_end=_iso(next_end),
                             chats_used=0, updated_at=_iso(now),
                             billing_mode="autopay" if is_autopay else "manual",
                             merchant_subscription_id=msid,
                             phonepe_subscription_id=phonepe_subscription_id,
                             mandate_state=m_state,
                             mandate_expires_at=exp_iso,
                             next_billing_at=_iso(next_end) if is_autopay and m_state == "ACTIVE" else "",
                             notified_order_id="", notified_at=""))
    return pay


def mark_cancelled(token: str) -> None:
    with _engine().begin() as conn:
        conn.execute(update(payments).where(payments.c.token == token, payments.c.status == "created")
                     .values(status="cancelled"))


def update_mandate_state(merchant_subscription_id: str, state: str, phonepe_subscription_id: str = "") -> str | None:
    """Update AutoPay mandate state from PhonePe webhook/poll. Returns affected phone_number or None."""
    if not merchant_subscription_id:
        return None
    engine = _engine()
    with engine.begin() as conn:
        row = conn.execute(select(subscriptions).where(
            subscriptions.c.merchant_subscription_id == merchant_subscription_id)).mappings().first()
        if not row:
            return None
        vals = {"mandate_state": state.upper(), "updated_at": _iso(_now())}
        if phonepe_subscription_id:
            vals["phonepe_subscription_id"] = phonepe_subscription_id
        if state.upper() in ("CANCELLED", "REVOKED", "EXPIRED", "COMPLETED"):
            vals["next_billing_at"] = ""
            vals["notified_order_id"] = ""
            vals["notified_at"] = ""
        conn.execute(update(subscriptions).where(subscriptions.c.phone_number == row["phone_number"]).values(**vals))
        return row["phone_number"]


def mark_renewal_paid(merchant_subscription_id: str, merchant_order_id: str, gateway_ref: str,
                      amount_paise: int) -> dict | None:
    """Record a completed monthly AutoPay renewal and extend the customer's plan by 1 month (idempotent)."""
    if not merchant_subscription_id:
        return None
    now = _now()
    engine = _engine()
    with engine.begin() as conn:
        sub = conn.execute(select(subscriptions).where(
            subscriptions.c.merchant_subscription_id == merchant_subscription_id)).mappings().first()
        if not sub:
            return None
        ref = gateway_ref or merchant_order_id
        dup = conn.execute(select(payments.c.id).where(payments.c.gateway_ref == ref).limit(1)).first()
        if dup:
            return None
        plan_key = norm_plan(sub["plan"])
        if plan_key == "free":
            last = conn.execute(select(payments).where(
                payments.c.merchant_subscription_id == merchant_subscription_id,
                payments.c.status == "paid",
            ).order_by(payments.c.id.desc()).limit(1)).mappings().first()
            plan_key = norm_plan(last["plan"]) if last else "standard"
        exp = _dt(sub.get("mandate_expires_at", ""))
        anchor = _dt(sub.get("next_billing_at", "")) or now
        if anchor < now - timedelta(days=5):
            anchor = now
        next_end = _add_months(anchor, 1)
        still_valid = not exp or next_end < exp
        pay_row = {
            "token": f"ren_{secrets.token_urlsafe(12)}",
            "phone_number": sub["phone_number"],
            "plan": plan_key,
            "amount": int(amount_paise) // 100 if amount_paise else PLANS[plan_key]["price"],
            "status": "paid",
            "gateway": "phonepe",
            "gateway_ref": ref,
            "merchant_subscription_id": merchant_subscription_id,
            "payment_type": "renewal",
            "created_at": _iso(now),
            "paid_at": _iso(now),
        }
        conn.execute(insert(payments).values(**pay_row))
        conn.execute(update(subscriptions).where(subscriptions.c.phone_number == sub["phone_number"]).values(
            plan=plan_key,
            period_start=_iso(now),
            period_end=_iso(next_end),
            chats_used=0,
            mandate_state="ACTIVE" if still_valid else "COMPLETED",
            next_billing_at=_iso(next_end) if still_valid else "",
            notified_order_id="",
            notified_at="",
            updated_at=_iso(now),
        ))
        return pay_row


def activation_message(pay: dict) -> str:
    p = plan_info(pay["plan"])
    sub = get(pay["phone_number"])
    chats = "Unlimited chats" if p["chats"] is None else f"{p['chats']} chats"
    if sub.get("mandate_state") == "ACTIVE":
        note = (f"next renewal on {_date(sub['period_end'])} "
                f"(3-year AutoPay valid till {_date(sub.get('mandate_expires_at', ''))}).")
    else:
        note = f"valid till {_date(sub['period_end'])}."
    return (f"✅ Payment of *₹{pay['amount']}* received. Thank you! 🙏\n\n"
            f"{p['icon']} Your *{p['name']}* plan is now active: {chats}/month, {note}\n\n"
            "Please continue with your question.")


def process_autopay_renewals() -> dict:
    """Run PhonePe AutoPay 24h pre-debit notifications and due monthly redemptions. Safe to run repeatedly."""
    from . import bot, phonepe
    if not (phonepe.enabled() and phonepe.autopay_enabled()):
        return {"skipped": "phonepe autopay not enabled"}
    if not _renewal_lock.acquire(blocking=False):
        return {"skipped": "already running"}
    stats = {"checked": 0, "notified": 0, "redeemed": 0, "renewed": 0, "errors": 0}
    try:
        now = _now()
        engine = _engine()
        with engine.connect() as conn:
            rows = conn.execute(select(subscriptions).where(
                subscriptions.c.billing_mode == "autopay",
                subscriptions.c.mandate_state == "ACTIVE",
            )).mappings().all()

        for row in rows:
            sub = dict(row)
            msid = sub.get("merchant_subscription_id", "")
            phone = sub["phone_number"]
            if not msid:
                continue
            stats["checked"] += 1
            try:
                exp = _dt(sub.get("mandate_expires_at", ""))
                if exp and now >= exp:
                    update_mandate_state(msid, "EXPIRED")
                    continue

                live = phonepe.subscription_status(msid)
                if live.get("state") and live["state"].upper() != "ACTIVE":
                    update_mandate_state(msid, live["state"], live.get("subscription_id", ""))
                    continue

                plan_key = norm_plan(sub.get("plan"))
                if plan_key == "free":
                    with engine.connect() as conn:
                        last = conn.execute(select(payments).where(
                            payments.c.merchant_subscription_id == msid,
                            payments.c.status == "paid",
                        ).order_by(payments.c.id.desc()).limit(1)).mappings().first()
                    if not last:
                        continue
                    plan_key = norm_plan(last["plan"])
                price = PLANS[plan_key]["price"]
                due = _dt(sub.get("next_billing_at", "")) or _dt(sub.get("period_end", ""))
                if not due:
                    continue

                notified_id = sub.get("notified_order_id", "")
                notified_at = _dt(sub.get("notified_at", ""))
                if not notified_id and now >= due - NOTIFY_LEAD:
                    order_id = f"REN{phone[-6:]}{int(now.timestamp())}"[:63]
                    phonepe.notify_redemption(order_id, msid, price, epoch_ms(due + timedelta(days=2)))
                    with engine.begin() as conn:
                        conn.execute(update(subscriptions).where(subscriptions.c.phone_number == phone).values(
                            notified_order_id=order_id, notified_at=_iso(now), updated_at=_iso(now)))
                    stats["notified"] += 1
                    continue

                if notified_id and now >= due and notified_at and now >= notified_at + REDEEM_MIN_WAIT:
                    phonepe.execute_redemption(notified_id, msid, price)
                    stats["redeemed"] += 1
                    st = phonepe.redemption_order_status(notified_id)
                    if st["state"] == "COMPLETED":
                        pay = mark_renewal_paid(msid, notified_id, st["transaction_id"] or notified_id, st["amount"])
                        if pay:
                            stats["renewed"] += 1
                            try:
                                bot.reply(phone, activation_message(pay))
                            except Exception:
                                log.exception("Could not send AutoPay renewal message to %s", phone)
            except Exception:
                stats["errors"] += 1
                log.exception("AutoPay renewal processing failed for %s (%s)", phone, msid)
        return stats
    finally:
        _renewal_lock.release()


# ---------------------------------------------------------------- dashboard
def all_subscriptions() -> dict[str, dict]:
    with _engine().connect() as conn:
        rows = conn.execute(select(subscriptions)).mappings().all()
    return {r["phone_number"]: dict(r) for r in rows}


def all_payments() -> list[dict]:
    with _engine().connect() as conn:
        rows = conn.execute(select(payments).order_by(payments.c.id.desc())).mappings().all()
    return [dict(r) for r in rows]


def is_active(sub: dict) -> bool:
    end = _dt(sub.get("period_end", ""))
    return bool(end and _now() < end)
