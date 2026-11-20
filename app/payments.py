"""Dummy payment gateway (TEST MODE - no real money).

  GET  /pay/{token}          checkout page for the link the bot sends on WhatsApp
  POST /pay/{token}/success  "Pay" button   -> payment marked paid, plan starts, customer gets a WhatsApp confirmation
  POST /pay/{token}/cancel   "Cancel" button

Paying needs a button press (POST), so WhatsApp's link preview (a GET) can never pay by itself.
To go live later, replace these pages with a real gateway (e.g. Razorpay) and call plans.mark_paid() from its webhook.
"""
import html
import logging
import secrets

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import bot, plans

log = logging.getLogger("astrovinod")
router = APIRouter(prefix="/pay")

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>AstroVinod – Payment</title>
<meta name="robots" content="noindex"><style>
body{{margin:0;font:15px/1.5 "Segoe UI",system-ui,Roboto,sans-serif;background:#f0f2f5;color:#111b21}}
.top{{background:#008069;height:140px}}
.card{{max-width:420px;margin:-100px auto 24px;background:#fff;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.12);padding:26px 24px}}
.test{{background:#fff3c4;color:#8a6300;font-size:12.5px;font-weight:600;padding:6px 10px;border-radius:6px;text-align:center;margin-bottom:16px}}
h1{{margin:0 0 4px;font-size:20px}} .muted{{color:#667781;font-size:13.5px}}
.amount{{font-size:34px;font-weight:700;margin:16px 0 4px}}
.row{{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #e9edef;font-size:14px}}
.row:last-of-type{{border:0}}
button{{width:100%;border:0;border-radius:24px;padding:13px;font:inherit;font-weight:600;cursor:pointer;margin-top:12px}}
.pay{{background:#00a884;color:#fff}} .cancel{{background:#fff;color:#667781;border:1px solid #e9edef}}
.big{{font-size:52px;text-align:center}} .center{{text-align:center}}
</style></head><body><div class="top"></div><div class="card">{body}</div></body></html>"""


def _page(body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(body=body), status_code=status)


def _message(icon: str, title: str, text: str, status: int = 200) -> HTMLResponse:
    return _page(f'<div class="big">{icon}</div><h1 class="center">{title}</h1><p class="center muted">{text}</p>', status)


def _mask(phone: str) -> str:
    return "+" + phone[:2] + " " + "x" * max(0, len(phone) - 6) + phone[-4:] if len(phone) > 6 else phone


@router.get("/{token}", response_class=HTMLResponse)
def checkout(token: str):
    pay = plans.get_payment(token)
    if not pay:
        return _message("⚠️", "Link not found", "Please reply PLANS on WhatsApp to get a new payment link.", 404)
    if pay["status"] == "paid":
        return _message("✅", "Already paid", "This plan is active. You can go back to WhatsApp.")
    if pay["status"] != "created" or plans.link_expired(pay):
        return _message("⌛", "Link expired", "Please reply PLANS on WhatsApp to get a new payment link.")
    p = plans.PLANS[pay["plan"]]
    chats = "Unlimited" if p["chats"] is None else str(p["chats"])
    t = html.escape(token)
    return _page(f"""
      <div class="test">TEST MODE – dummy payment, no real money is charged</div>
      <h1>AstroVinod AI</h1><div class="muted">Astrology consultation on WhatsApp</div>
      <div class="amount">₹{pay['amount']}</div>
      <div class="row"><span>Plan</span><b>{p['icon']} {p['name']}</b></div>
      <div class="row"><span>Chats</span><b>{chats} / month</b></div>
      <div class="row"><span>Validity</span><b>30 days</b></div>
      <div class="row"><span>WhatsApp number</span><b>{html.escape(_mask(pay['phone_number']))}</b></div>
      <form method="post" action="/pay/{t}/success"><button class="pay">Pay ₹{pay['amount']}</button></form>
      <form method="post" action="/pay/{t}/cancel"><button class="cancel">Cancel</button></form>""")


@router.post("/{token}/success", response_class=HTMLResponse)
def success(token: str):
    pay = plans.get_payment(token)
    if not pay:
        return _message("⚠️", "Link not found", "Please reply PLANS on WhatsApp to get a new payment link.", 404)
    if pay["status"] == "paid":
        return _message("✅", "Already paid", "This plan is active. You can go back to WhatsApp.")
    if pay["status"] != "created" or plans.link_expired(pay):
        return _message("⌛", "Link expired", "Please reply PLANS on WhatsApp to get a new payment link.")
    pay = plans.mark_paid(token, gateway_ref="TEST-" + secrets.token_hex(6).upper())
    if not pay:
        return _message("✅", "Already paid", "This plan is active. You can go back to WhatsApp.")
    log.info("Dummy payment %s: %s bought %s", pay["gateway_ref"], pay["phone_number"], pay["plan"])
    try:
        bot.reply(pay["phone_number"], plans.activation_message(pay))
    except Exception:
        log.exception("Could not send the plan confirmation to %s", pay["phone_number"])
    p = plans.PLANS[pay["plan"]]
    return _message("✅", "Payment successful",
                    f"Your <b>{p['name']}</b> plan is active. Reference {html.escape(pay['gateway_ref'])}.<br>"
                    "You can close this page and continue on WhatsApp.")


@router.post("/{token}/cancel", response_class=HTMLResponse)
def cancel(token: str):
    plans.mark_cancelled(token)
    return _message("❌", "Payment cancelled", "No money was taken. Reply PLANS on WhatsApp anytime to try again.")
