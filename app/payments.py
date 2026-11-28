"""Checkout pages for subscription plans.

  GET  /pay/{token}            checkout page for the link the bot sends on WhatsApp
  POST /pay/{token}/start      PhonePe: create the order and go to PhonePe's payment page
  GET  /pay/{token}/done       PhonePe sends the customer back here; status is checked with PhonePe
  POST /pay/phonepe/webhook    PhonePe server-to-server notification (status is re-checked with PhonePe)
  POST /pay/{token}/success    TEST MODE only (when PhonePe keys are not set): dummy "Pay" button
  POST /pay/{token}/cancel     Cancel

A plan is switched on only after PhonePe's Order Status API says COMPLETED for the right amount.
Paying needs a button press (POST), so WhatsApp's link preview (a GET) can never start a payment by itself.
"""
import hashlib
import hmac
import html
import logging
import os
import re
import secrets
import time
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import bot, phonepe, plans

log = logging.getLogger("astrovinod")
router = APIRouter(prefix="/pay")
web_router = APIRouter()

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>AstroVinod – Payment</title>
<meta name="robots" content="noindex">{head}<style>
body{{margin:0;font:15px/1.5 "Segoe UI",system-ui,Roboto,sans-serif;background:#f0f2f5;color:#111b21}}
.top{{background:#008069;height:140px}}
.card{{max-width:420px;margin:-100px auto 24px;background:#fff;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.12);padding:26px 24px}}
.test{{background:#fff3c4;color:#8a6300;font-size:12.5px;font-weight:600;padding:6px 10px;border-radius:6px;text-align:center;margin-bottom:16px}}
h1{{margin:0 0 4px;font-size:20px}} .muted{{color:#667781;font-size:13.5px}}
.amount{{font-size:34px;font-weight:700;margin:16px 0 4px}}
.row{{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #e9edef;font-size:14px}}
.row:last-of-type{{border:0}}
button{{width:100%;border:0;border-radius:24px;padding:13px;font:inherit;font-weight:600;cursor:pointer;margin-top:12px}}
.pay{{background:#00a884;color:#fff}} .phonepe{{background:#5f259f;color:#fff}}
.cancel{{background:#fff;color:#667781;border:1px solid #e9edef}}
.big{{font-size:52px;text-align:center}} .center{{text-align:center}}
.secure{{text-align:center;color:#667781;font-size:12px;margin-top:14px}}
</style></head><body><div class="top"></div><div class="card">{body}</div></body></html>"""

NEW_LINK = "Please reply PLANS on WhatsApp to get a new payment link."
ACTIVE = "This plan is active. You can go back to WhatsApp."


def _page(body: str, status: int = 200, head: str = "") -> HTMLResponse:
    return HTMLResponse(_PAGE.format(body=body, head=head), status_code=status)


def _message(icon: str, title: str, text: str, status: int = 200, extra: str = "", head: str = "") -> HTMLResponse:
    return _page(f'<div class="big">{icon}</div><h1 class="center">{title}</h1>'
                 f'<p class="center muted">{text}</p>{extra}', status, head)


def _mask(phone: str) -> str:
    return "+" + phone[:2] + " " + "x" * max(0, len(phone) - 6) + phone[-4:] if len(phone) > 6 else phone


def _usable(token: str) -> tuple[dict | None, HTMLResponse | None]:
    """The payment if it can still be paid, else the page to show instead."""
    pay = plans.get_payment(token)
    if not pay:
        return None, _message("⚠️", "Link not found", NEW_LINK, 404)
    if pay["status"] == "paid":
        return None, _message("✅", "Already paid", ACTIVE)
    if pay["status"] != "created" or plans.link_expired(pay):
        return None, _message("⌛", "Link expired", NEW_LINK)
    return pay, None


def _finish(token: str, ref: str, phonepe_subscription_id: str = "", mandate_state: str = "") -> dict | None:
    """Switch the plan on (once) and confirm on WhatsApp. None if it was already done."""
    pay = plans.mark_paid(token, gateway_ref=ref, phonepe_subscription_id=phonepe_subscription_id,
                          mandate_state=mandate_state)
    if not pay:
        return None
    log.info("Payment %s (%s): %s bought %s", ref, pay["gateway"], pay["phone_number"], pay["plan"])
    try:
        bot.reply(pay["phone_number"], plans.activation_message(pay))
    except Exception:
        log.exception("Could not send the plan confirmation to %s", pay["phone_number"])
    return pay


def _paid_page(pay: dict) -> HTMLResponse:
    p = plans.plan_info(pay["plan"])
    extra = " with monthly AutoPay (3-year mandate)" if pay.get("merchant_subscription_id") or pay["gateway"] == "dummy" else ""
    return _message("✅", "Subscription active",
                    f"Your <b>{p['name']}</b> monthly plan is active{extra}. Reference {html.escape(pay['gateway_ref'])}.<br>"
                    "You can close this page and continue on WhatsApp.")


def _verify_phonepe(token: str, merchant_order_id: str) -> str:
    """Ask PhonePe for the real status. Switches the plan on when COMPLETED. Returns the state."""
    pay = plans.get_payment(token)
    if not pay or not merchant_order_id:
        return "UNKNOWN"
    if pay["status"] == "paid":
        return "COMPLETED"
    st = phonepe.order_status(merchant_order_id)
    if st["state"] == "COMPLETED":
        if st["amount"] != pay["amount"] * 100:
            log.error("PhonePe amount mismatch for %s: paid %s paise, expected %s", token, st["amount"], pay["amount"])
            return "MISMATCH"
        pp_sub_id, m_state = "", "ACTIVE"
        msid = pay.get("merchant_subscription_id", "")
        if msid:
            try:
                sub_st = phonepe.subscription_status(msid)
                pp_sub_id = sub_st.get("subscription_id", "")
                if sub_st.get("state"):
                    m_state = sub_st["state"].upper()
            except Exception:
                log.warning("Could not fetch PhonePe subscription status for %s", msid)
        _finish(token, st["transaction_id"] or merchant_order_id, pp_sub_id, m_state)
    return st["state"]


def _handle_webhook(data: dict) -> str:
    payload = data.get("payload") or {}
    pf = payload.get("paymentFlow") or {}
    event = str(data.get("event") or data.get("type") or "").upper()
    msid = payload.get("merchantSubscriptionId") or pf.get("merchantSubscriptionId") or (payload.get("metaInfo") or {}).get("udf2", "")
    pp_sub_id = payload.get("subscriptionId") or pf.get("subscriptionId", "")
    mid = payload.get("merchantOrderId") or payload.get("originalMerchantOrderId", "")
    token = (payload.get("metaInfo") or {}).get("udf1") or (mid.rsplit("-", 1)[0] if "-" in mid else "")

    if "REDEMPTION" in event:
        state = str(payload.get("state") or "").upper()
        if state == "COMPLETED" and msid:
            txn = next((p.get("transactionId") for p in (payload.get("paymentDetails") or [])
                        if p.get("state") == "COMPLETED" and p.get("transactionId")), mid)
            pay = plans.mark_renewal_paid(msid, mid, txn, int(payload.get("amount") or 0))
            if pay:
                try:
                    bot.reply(pay["phone_number"], plans.activation_message(pay))
                except Exception:
                    log.exception("Could not send renewal confirmation to %s", pay["phone_number"])
        elif state == "FAILED" and msid:
            phone = plans.update_mandate_state(msid, "ACTIVE", pp_sub_id)
            if phone:
                try:
                    bot.reply(phone, "⚠️ Your monthly PhonePe AutoPay renewal could not be completed. "
                                     "Please check your UPI AutoPay mandate or reply *PLANS* to re-subscribe.")
                except Exception:
                    log.exception("Could not send renewal failure notice to %s", phone)
        return state or event

    for state_name in ("PAUSED", "UNPAUSED", "CANCELLED", "REVOKED", "EXPIRED", "COMPLETED", "ACTIVE", "ACTIVATED"):
        if state_name in event and "SETUP" not in event and "ORDER" not in event:
            mapped = "ACTIVE" if state_name in ("UNPAUSED", "ACTIVATED") else state_name
            plans.update_mandate_state(msid, mapped, pp_sub_id)
            return mapped

    if mid and token:
        return _verify_phonepe(token, mid)
    if msid and payload.get("state"):
        plans.update_mandate_state(msid, str(payload["state"]), pp_sub_id)
        return str(payload["state"])
    return event or "IGNORED"


# ---------------------------------------------------------------- PhonePe webhook (must be above /{token} routes)
@router.post("/phonepe/webhook")
async def phonepe_webhook(request: Request):
    if not phonepe.webhook_authorised(request.headers.get("authorization")):
        log.warning("PhonePe webhook with a wrong Authorization header was ignored")
        return JSONResponse({"ok": False}, status_code=401)
    try:
        data = await request.json()
        from starlette.concurrency import run_in_threadpool
        state = await run_in_threadpool(_handle_webhook, data)
        log.info("PhonePe webhook %s: %s", data.get("event") or data.get("type"), state)
    except Exception:
        log.exception("PhonePe webhook could not be processed")
    return {"ok": True}  # always 2xx quickly; the customer's return page also checks the status


# ---------------------------------------------------------------- checkout page
@router.get("/{token}", response_class=HTMLResponse)
def checkout(token: str):
    pay, page = _usable(token)
    if page:
        return page
    p = plans.plan_info(pay["plan"])
    chats = "Unlimited" if p["chats"] is None else str(p["chats"])
    t = html.escape(token)
    real = pay["gateway"] == "phonepe" and phonepe.enabled()
    autopay = phonepe.autopay_enabled()
    if real:
        top = ""
        btn_label = f'Enable AutoPay &amp; Pay ₹{pay["amount"]}' if autopay else f'Pay ₹{pay["amount"]} with PhonePe'
        button = f'<form method="post" action="/pay/{t}/start"><button class="phonepe">{btn_label}</button></form>'
        foot = ('<div class="secure">🔒 PhonePe UPI AutoPay · Monthly auto-renewal for 3 years · Cancel anytime</div>'
                if autopay else '<div class="secure">🔒 Secure payment by PhonePe · UPI, cards, netbanking</div>')
    else:
        top = '<div class="test">TEST MODE – dummy AutoPay payment, no real money is charged</div>'
        button = f'<form method="post" action="/pay/{t}/success"><button class="pay">Enable AutoPay &amp; Pay ₹{pay["amount"]}</button></form>'
        foot = ""
    billing_txt = "Monthly AutoPay (3-year mandate)" if autopay or not real else "30 days"
    return _page(f"""
      {top}
      <h1>AstroVinod AI</h1><div class="muted">Monthly Astrology Subscription on WhatsApp</div>
      <div class="amount">₹{pay['amount']}<span style="font-size:15px;font-weight:400;color:#667781"> / month</span></div>
      <div class="row"><span>Plan</span><b>{p['icon']} {p['name']}</b></div>
      <div class="row"><span>Chats</span><b>{chats} / month</b></div>
      <div class="row"><span>Billing</span><b>{billing_txt}</b></div>
      <div class="row"><span>WhatsApp number</span><b>{html.escape(_mask(pay['phone_number']))}</b></div>
      {button}
      <form method="post" action="/pay/{t}/cancel"><button class="cancel">Cancel</button></form>
      {foot}""")


# ---------------------------------------------------------------- PhonePe flow
@router.post("/{token}/start")
def start(token: str):
    pay, page = _usable(token)
    if page:
        return page
    if not phonepe.enabled():
        return RedirectResponse(f"/pay/{token}", status_code=303)
    ts = int(time.time())
    mid = f"{token}-{ts}"[:63]  # new order id per attempt (PhonePe ids can't be reused)
    p = plans.plan_info(pay["plan"])
    redirect_url = f"{plans.public_url()}/pay/{token}/done"
    msid = ""
    try:
        if phonepe.autopay_enabled():
            msid = f"MS{pay['id']}T{ts}"[:63]
            exp_ms = plans.epoch_ms(plans.mandate_expiry())
            url = phonepe.create_subscription_setup(
                mid, msid, pay["amount"], redirect_url, token, exp_ms, f"AstroVinod {p['name']} Monthly"
            )
        else:
            url = phonepe.create_payment(mid, pay["amount"], redirect_url, token, f"AstroVinod {p['name']} plan")
    except Exception:
        log.exception("PhonePe create payment failed for %s", token)
        return _message("⚠️", "Payment could not start",
                        "PhonePe is not responding right now. Please try again in a minute.",
                        extra=f'<form method="get" action="/pay/{html.escape(token)}"><button class="pay">Try again</button></form>')
    plans.set_gateway_ref(token, mid, msid)
    return RedirectResponse(url, status_code=303)


@router.get("/{token}/done", response_class=HTMLResponse)
def done(token: str):
    pay = plans.get_payment(token)
    if not pay:
        return _message("⚠️", "Link not found", NEW_LINK, 404)
    if pay["status"] == "paid":
        return _paid_page(pay)
    try:
        state = _verify_phonepe(token, pay["gateway_ref"])
    except Exception:
        log.exception("PhonePe status check failed for %s", token)
        state = "PENDING"
    if state == "COMPLETED":
        return _paid_page(plans.get_payment(token))
    t = html.escape(token)
    if state == "PENDING":
        return _message("⏳", "Checking your payment…",
                        "If you completed the payment, your plan will be switched on in a moment and you'll get a "
                        "WhatsApp message. This page refreshes by itself.",
                        extra=f'<form method="get" action="/pay/{t}"><button class="cancel">I did not pay – pay again</button></form>',
                        head=f'<meta http-equiv="refresh" content="5;url=/pay/{t}/done">')
    if state == "MISMATCH":
        return _message("⚠️", "Payment needs checking",
                        "We received a payment with an unexpected amount. Please message us on WhatsApp.")
    return _message("❌", "Payment not completed", "No money was taken. You can try again.",
                    extra=f'<form method="get" action="/pay/{t}"><button class="phonepe">Try again</button></form>')


# ---------------------------------------------------------------- test mode / cancel
@router.post("/{token}/success", response_class=HTMLResponse)
def success(token: str):
    pay, page = _usable(token)
    if page:
        return page
    if phonepe.enabled() or pay["gateway"] != "dummy":  # never free plans once a real gateway is on
        return RedirectResponse(f"/pay/{token}", status_code=303)
    paid = _finish(token, "TEST-" + secrets.token_hex(6).upper())
    return _paid_page(paid) if paid else _message("✅", "Already paid", ACTIVE)


@router.post("/{token}/cancel", response_class=HTMLResponse)
def cancel(token: str):
    plans.mark_cancelled(token)
    return _message("❌", "Payment cancelled", "No money was taken. Reply PLANS on WhatsApp anytime to try again.")


# ---------------------------------------------------------------- Website checkout & reviewer login
def _reviewer_creds() -> tuple[str, str]:
    return os.getenv("REVIEWER_USER", "").strip(), os.getenv("REVIEWER_PASS", "").strip()


def _reviewer_cookie(user: str, pw: str) -> str:
    return hmac.new(pw.encode(), f"reviewer:{user}".encode(), hashlib.sha256).hexdigest()


def _is_reviewer(request: Request) -> bool:
    user, pw = _reviewer_creds()
    if not user or not pw:
        return False
    cookie = request.cookies.get("astrovinod_reviewer", "")
    return bool(cookie) and hmac.compare_digest(cookie, _reviewer_cookie(user, pw))


def _parse_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)
    return {k: v[0].strip() for k, v in parsed.items() if v}


def _norm_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = "91" + digits
    return digits if 10 <= len(digits) <= 15 else ""


_FORM_CSS = """<style>
label{display:block;font-size:13px;font-weight:600;margin:12px 0 5px;color:#3b4a54}
input,select{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #d1d7db;border-radius:8px;font:inherit}
.err{background:#fdecea;color:#b42318;padding:8px 10px;border-radius:6px;font-size:13px;margin:10px 0}
.ok{background:#e7f8f0;color:#027a48;padding:8px 10px;border-radius:6px;font-size:13px;margin:10px 0}
.links{display:flex;justify-content:space-between;font-size:13px;margin-top:14px}
.links a{color:#008069;text-decoration:none}
</style>"""


def _login_html(plan: str = "", username: str = "", error: str = "", status: int = 200) -> HTMLResponse:
    p_input = f'<input type="hidden" name="plan" value="{html.escape(plan)}">' if plan in plans.PAID else ""
    err_box = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return _page(f"""
      <h1>AstroVinod AI</h1><div class="muted">Member &amp; Reviewer Portal</div>
      {err_box}
      <form method="post" action="/login">
        {p_input}
        <label for="username">Username</label>
        <input id="username" name="username" type="text" required autocomplete="username" value="{html.escape(username)}" placeholder="Enter username">
        <label for="password">Password</label>
        <input id="password" name="password" type="password" required autocomplete="current-password" placeholder="Enter password">
        <button class="phonepe" type="submit">Sign In</button>
      </form>
      <div class="links"><a href="/">&larr; Back to Home</a><a href="/subscribe">Subscribe with WhatsApp &rarr;</a></div>
    """, status=status, head=_FORM_CSS)


@web_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, plan: str = ""):
    if _is_reviewer(request):
        suffix = f"?plan={plan}" if plan in plans.PAID else ""
        return RedirectResponse(f"/subscribe{suffix}", status_code=303)
    user, pw = _reviewer_creds()
    if not user or not pw:
        return _message("🔒", "Login unavailable", "Reviewer login is not configured on the server.", 503)
    return _login_html(plan=plan)


@web_router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request):
    user, pw = _reviewer_creds()
    if not user or not pw:
        return _message("🔒", "Login unavailable", "Reviewer login is not configured on the server.", 503)
    form = _parse_form(await request.body())
    u_ok = hmac.compare_digest(form.get("username", "").encode(), user.encode())
    p_ok = hmac.compare_digest(form.get("password", "").encode(), pw.encode())
    plan = form.get("plan", "")
    if not (u_ok and p_ok):
        return _login_html(plan=plan, username=form.get("username", ""), error="Invalid username or password.", status=401)
    suffix = f"?plan={plan}" if plan in plans.PAID else ""
    resp = RedirectResponse(f"/subscribe{suffix}", status_code=303)
    resp.set_cookie("astrovinod_reviewer", _reviewer_cookie(user, pw), httponly=True, samesite="lax", max_age=86400)
    return resp


@web_router.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("astrovinod_reviewer")
    return resp


@web_router.get("/subscribe", response_class=HTMLResponse)
def subscribe_page(request: Request, plan: str = "standard", error: str = ""):
    chosen = plan.strip().lower()
    if chosen not in plans.PAID:
        chosen = "standard"
    reviewer = _is_reviewer(request)
    banner = ('<div class="ok">Signed in as PhonePe Reviewer. Select a plan to inspect PhonePe AutoPay checkout.</div>'
              if reviewer else "")
    err_box = f'<div class="err">{html.escape(error)}</div>' if error else ""
    opts = []
    for key in plans.PAID:
        p = plans.PLANS[key]
        chats = "Unlimited chats" if p["chats"] is None else f"{p['chats']} chats/month"
        sel = " selected" if key == chosen else ""
        opts.append(f'<option value="{key}"{sel}>{p["icon"]} {p["name"]} — ₹{p["price"]}/month ({chats})</option>')
    default_phone = "919999999999" if reviewer else ""
    phone_hint = "Demo reviewer WhatsApp number prefilled" if reviewer else "Enter 10-digit WhatsApp mobile number"
    footer_link = '<a href="/logout">Sign Out</a>' if reviewer else '<a href="/login">Reviewer Sign In &rarr;</a>'
    return _page(f"""
      <h1>AstroVinod AI</h1><div class="muted">WhatsApp Monthly Subscription</div>
      {banner}{err_box}
      <form method="post" action="/subscribe">
        <label for="plan">Subscription Plan</label>
        <select id="plan" name="plan">{"".join(opts)}</select>
        <label for="phone">WhatsApp Number</label>
        <input id="phone" name="phone" type="tel" required value="{default_phone}" placeholder="{phone_hint}">
        <button class="phonepe" type="submit">Proceed to Checkout</button>
      </form>
      <div class="links"><a href="/">&larr; Back to Home</a>{footer_link}</div>
    """, head=_FORM_CSS)


@web_router.post("/subscribe", response_class=HTMLResponse)
async def subscribe_submit(request: Request):
    form = _parse_form(await request.body())
    plan = form.get("plan", "standard").strip().lower()
    if plan not in plans.PAID:
        plan = "standard"
    phone = _norm_phone(form.get("phone", ""))
    if not phone:
        return subscribe_page(request, plan=plan, error="Please enter a valid 10-to-15 digit WhatsApp number.")
    token = plans.create_payment(phone, plan)
    return RedirectResponse(f"/pay/{token}", status_code=303)
