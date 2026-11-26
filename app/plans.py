"""Subscription plans: monthly chat limits, plan purchases and payments.

Plans                 FREE 10 chats / STANDARD 150 / PREMIUM 300 / VIP unlimited, per 30 days.
What counts as a chat Every question after the birth profile is set up (registration and the first report are free).
Period               30 days. FREE restarts every 30 days; a paid plan lasts 30 days from payment, then back to FREE.

Tables (created automatically):
  subscriptions  one row per customer: current plan, period start/end, chats used in this period
  payments       every payment attempt (link created / paid / cancelled)
"""
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Integer, MetaData, String, Table, insert, select, update

PERIOD = timedelta(days=30)
LINK_VALID = timedelta(hours=24)

PLANS = {
    "free":     {"name": "FREE",     "price": 0,    "chats": 10,   "icon": "🆓"},
    "standard": {"name": "STANDARD", "price": 299,  "chats": 150,  "icon": "⭐"},
    "premium":  {"name": "PREMIUM",  "price": 499,  "chats": 300,  "icon": "💎"},
    "vip":      {"name": "VIP",      "price": 4999, "chats": None, "icon": "👑"},  # None = unlimited
}
PAID = ("standard", "premium", "vip")
_LEGACY_PLANS = {"gold": "standard", "platinum": "premium"}
PLAN_IMAGE = "static/plans.jpg"


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
)

_ready = False
_ready_lock = threading.Lock()


def _engine():
    global _ready
    from . import bot
    engine = bot.store().engine
    if not _ready:
        with _ready_lock:
            if not _ready:
                meta.create_all(engine)
                _ready = True
    return engine


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
    """Current subscription; starts FREE, rolls over to a new 30-day period (and back to FREE) when one ends."""
    engine = _engine()
    now = _now()
    with engine.begin() as conn:
        row = conn.execute(select(subscriptions).where(subscriptions.c.phone_number == phone)).mappings().first()
        if not row:
            sub = {"phone_number": phone, "plan": "free", "period_start": _iso(now),
                   "period_end": _iso(now + PERIOD), "chats_used": 0, "updated_at": _iso(now)}
            conn.execute(insert(subscriptions).values(**sub))
            return sub
        sub = dict(row)
        end = _dt(sub["period_end"])
        if not end or now >= end:
            sub.update(plan="free", period_start=_iso(now), period_end=_iso(now + PERIOD), chats_used=0,
                       updated_at=_iso(now))
            conn.execute(update(subscriptions).where(subscriptions.c.phone_number == phone)
                         .values(**{k: v for k, v in sub.items() if k != "phone_number"}))
        return sub


def remaining(sub: dict) -> int | None:
    limit = plan_info(sub.get("plan"))["chats"]
    return None if limit is None else max(0, limit - sub["chats_used"])


def use_chat_status(phone: str) -> tuple[str, bool]:
    """Count one chat. Returns (message, exhausted_now)."""
    sub = get(phone)
    with _engine().begin() as conn:
        conn.execute(update(subscriptions).where(subscriptions.c.phone_number == phone)
                     .values(chats_used=subscriptions.c.chats_used + 1, updated_at=_iso(_now())))
    sub["chats_used"] += 1
    left = remaining(sub)
    if left is None or left > 2:
        return "", False
    name = plan_info(sub.get("plan"))["name"]
    if left == 0:
        return (f"ℹ️ That was the last chat of your *{name}* plan for this period.\n\n"
                "Choose a plan below to continue:"), True
    return f"ℹ️ {left} chat{'s' if left > 1 else ''} left in your *{name}* plan. Reply *PLANS* to upgrade anytime.", False


def use_chat(phone: str) -> str:
    """Count one chat. Returns a short note when the customer is running out ("" otherwise)."""
    msg, exhausted = use_chat_status(phone)
    if exhausted:
        name = plan_info(get(phone).get("plan"))["name"]
        return (f"ℹ️ That was the last chat of your *{name}* plan for this period. "
                "Reply *PLANS* to see options to continue.")
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
    until = "renews" if norm_plan(sub.get("plan")) == "free" else "valid till"
    head = f"{p['icon']} Your plan: *{p['name']}*\n💬 Chats this month: {used}\n📅 {until.capitalize()}: {_date(sub['period_end'])}"
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
    body = (f"{p['icon']} *{p['name']} plan* – {chats} for 30 days – *₹{p['price']}*\n\n"
            "Tap below to open the payment gateway link and pay securely.")
    fallback = (f"{p['icon']} *{p['name']} plan* – {chats} for 30 days – *₹{p['price']}*\n\n"
                f"Tap the link to pay securely:\n{url}\n\n"
                "_The link is valid for 24 hours. Your plan starts as soon as the payment is done._")
    return {"plan": plan, "price": p["price"], "url": url, "body": body,
            "button": f"Pay ₹{p['price']} Now", "footer": "Valid 24 hours · Secure checkout",
            "fallback": fallback}


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
def create_payment(phone: str, plan: str) -> str:
    from . import phonepe
    plan = norm_plan(plan)
    token = secrets.token_urlsafe(16)
    with _engine().begin() as conn:
        conn.execute(insert(payments).values(token=token, phone_number=phone, plan=plan,
                                             amount=PLANS[plan]["price"], status="created",
                                             gateway="phonepe" if phonepe.enabled() else "dummy",
                                             created_at=_iso(_now())))
    return token


def set_gateway_ref(token: str, ref: str) -> None:
    """Remember the gateway's order id for a payment attempt (before it is paid)."""
    with _engine().begin() as conn:
        conn.execute(update(payments).where(payments.c.token == token, payments.c.status == "created")
                     .values(gateway_ref=ref))


def get_payment(token: str) -> dict | None:
    with _engine().connect() as conn:
        row = conn.execute(select(payments).where(payments.c.token == token)).mappings().first()
    return dict(row) if row else None


def link_expired(pay: dict) -> bool:
    created = _dt(pay["created_at"])
    return not created or _now() - created > LINK_VALID


def mark_paid(token: str, gateway_ref: str) -> dict | None:
    """Mark a payment paid and start the plan for 30 days. Returns the payment, or None if it was not payable."""
    now = _now()
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
    with engine.begin() as conn:
        conn.execute(update(subscriptions).where(subscriptions.c.phone_number == pay["phone_number"])
                     .values(plan=pay["plan"], period_start=_iso(now), period_end=_iso(now + PERIOD),
                             chats_used=0, updated_at=_iso(now)))
    return pay


def mark_cancelled(token: str) -> None:
    with _engine().begin() as conn:
        conn.execute(update(payments).where(payments.c.token == token, payments.c.status == "created")
                     .values(status="cancelled"))


def activation_message(pay: dict) -> str:
    p = plan_info(pay["plan"])
    sub = get(pay["phone_number"])
    chats = "Unlimited chats" if p["chats"] is None else f"{p['chats']} chats"
    return (f"✅ Payment of *₹{pay['amount']}* received. Thank you! 🙏\n\n"
            f"{p['icon']} Your *{p['name']}* plan is now active: {chats}, valid till {_date(sub['period_end'])}.\n\n"
            "Please continue with your question.")


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
