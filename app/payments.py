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
import html
import logging
import secrets
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import bot, phonepe, plans

log = logging.getLogger("astrovinod")
router = APIRouter(prefix="/pay")

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


def _finish(token: str, ref: str) -> dict | None:
    """Switch the plan on (once) and confirm on WhatsApp. None if it was already done."""
    pay = plans.mark_paid(token, gateway_ref=ref)
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
    return _message("✅", "Payment successful",
                    f"Your <b>{p['name']}</b> plan is active. Reference {html.escape(pay['gateway_ref'])}.<br>"
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
        _finish(token, st["transaction_id"] or merchant_order_id)
    return st["state"]


# ---------------------------------------------------------------- PhonePe webhook (must be above /{token} routes)
@router.post("/phonepe/webhook")
async def phonepe_webhook(request: Request):
    if not phonepe.webhook_authorised(request.headers.get("authorization")):
        log.warning("PhonePe webhook with a wrong Authorization header was ignored")
        return JSONResponse({"ok": False}, status_code=401)
    try:
        data = await request.json()
        payload = data.get("payload") or {}
        mid = payload.get("merchantOrderId", "")
        token = (payload.get("metaInfo") or {}).get("udf1") or mid.rsplit("-", 1)[0]
        if mid and token:
            from starlette.concurrency import run_in_threadpool
            state = await run_in_threadpool(_verify_phonepe, token, mid)
            log.info("PhonePe webhook %s for %s: %s", data.get("event"), mid, state)
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
    if real:
        top = ""
        button = (f'<form method="post" action="/pay/{t}/start"><button class="phonepe">'
                  f'Pay ₹{pay["amount"]} with PhonePe</button></form>')
        foot = '<div class="secure">🔒 Secure payment by PhonePe · UPI, cards, netbanking</div>'
    else:
        top = '<div class="test">TEST MODE – dummy payment, no real money is charged</div>'
        button = f'<form method="post" action="/pay/{t}/success"><button class="pay">Pay ₹{pay["amount"]}</button></form>'
        foot = ""
    return _page(f"""
      {top}
      <h1>AstroVinod AI</h1><div class="muted">Astrology consultation on WhatsApp</div>
      <div class="amount">₹{pay['amount']}</div>
      <div class="row"><span>Plan</span><b>{p['icon']} {p['name']}</b></div>
      <div class="row"><span>Chats</span><b>{chats} / month</b></div>
      <div class="row"><span>Validity</span><b>30 days</b></div>
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
    mid = f"{token}-{int(time.time())}"[:63]  # new order id per attempt (PhonePe ids can't be reused)
    p = plans.plan_info(pay["plan"])
    try:
        url = phonepe.create_payment(mid, pay["amount"], f"{plans.public_url()}/pay/{token}/done", token,
                                     f"AstroVinod {p['name']} plan")
    except Exception:
        log.exception("PhonePe create payment failed for %s", token)
        return _message("⚠️", "Payment could not start",
                        "PhonePe is not responding right now. Please try again in a minute.",
                        extra=f'<form method="get" action="/pay/{html.escape(token)}"><button class="pay">Try again</button></form>')
    plans.set_gateway_ref(token, mid)
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
