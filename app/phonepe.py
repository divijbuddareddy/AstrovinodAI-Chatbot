"""PhonePe Payment Gateway v2 - Standard Checkout & UPI AutoPay Subscriptions (plain HTTPS, no SDK).

Render / .env settings:
  PHONEPE_CLIENT_ID, PHONEPE_CLIENT_SECRET, PHONEPE_CLIENT_VERSION   from PhonePe Business > Developer Settings > API Keys
  PHONEPE_ENV                    production (default) | sandbox
  PHONEPE_AUTOPAY                true (default) | false (set false only if Subscriptions aren't enabled yet)
  PHONEPE_WEBHOOK_USER / _PASS   optional: the username/password entered in PhonePe > Developer Settings > Webhooks

A payment is only ever treated as paid after PhonePe's Order Status API says COMPLETED.
"""
import hashlib
import hmac
import logging
import os
import threading
import time

import requests

log = logging.getLogger("astrovinod")

_URLS = {
    "production": {"token": "https://api.phonepe.com/apis/identity-manager/v1/oauth/token",
                   "pg": "https://api.phonepe.com/apis/pg"},
    "sandbox": {"token": "https://api-preprod.phonepe.com/apis/pg-sandbox/v1/oauth/token",
                "pg": "https://api-preprod.phonepe.com/apis/pg-sandbox"},
}
TIMEOUT = 20


class PhonePeError(Exception):
    pass


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def enabled() -> bool:
    return bool(_env("PHONEPE_CLIENT_ID") and _env("PHONEPE_CLIENT_SECRET"))


def autopay_enabled() -> bool:
    return _env("PHONEPE_AUTOPAY").lower() not in ("0", "false", "no", "off")


def _urls() -> dict:
    return _URLS["sandbox" if _env("PHONEPE_ENV").lower() in ("sandbox", "uat", "test") else "production"]


_token = {"value": "", "expires_at": 0.0}
_token_lock = threading.Lock()


def _auth_header() -> dict:
    with _token_lock:
        if not _token["value"] or time.time() > _token["expires_at"] - 300:
            r = requests.post(_urls()["token"], timeout=TIMEOUT, data={
                "client_id": _env("PHONEPE_CLIENT_ID"),
                "client_version": _env("PHONEPE_CLIENT_VERSION") or "1",
                "client_secret": _env("PHONEPE_CLIENT_SECRET"),
                "grant_type": "client_credentials",
            })
            if r.status_code != 200:
                raise PhonePeError(f"PhonePe login failed ({r.status_code}): {r.text[:300]}")
            d = r.json()
            _token["value"] = d["access_token"]
            _token["expires_at"] = float(d.get("expires_at") or time.time() + 3600)
        return {"Authorization": f"O-Bearer {_token['value']}", "Content-Type": "application/json"}


def create_payment(merchant_order_id: str, amount_rupees: int, redirect_url: str, payment_token: str,
                   message: str = "") -> str:
    """Create a checkout order; returns PhonePe's payment page URL to send the customer to."""
    body = {
        "merchantOrderId": merchant_order_id,
        "amount": int(amount_rupees) * 100,  # paise
        "expireAfter": 1200,
        "metaInfo": {"udf1": payment_token},
        "paymentFlow": {"type": "PG_CHECKOUT", "message": message[:100],
                        "merchantUrls": {"redirectUrl": redirect_url}},
    }
    r = requests.post(_urls()["pg"] + "/checkout/v2/pay", json=body, headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code != 200 or not r.json().get("redirectUrl"):
        raise PhonePeError(f"PhonePe create payment failed ({r.status_code}): {r.text[:300]}")
    return r.json()["redirectUrl"]


def create_subscription_setup(merchant_order_id: str, merchant_subscription_id: str, amount_rupees: int,
                              redirect_url: str, payment_token: str, expire_at_ms: int,
                              message: str = "") -> str:
    """Create a 3-year monthly AutoPay subscription setup order; returns PhonePe's checkout URL."""
    paise = int(amount_rupees) * 100
    body = {
        "merchantOrderId": merchant_order_id,
        "amount": paise,
        "expireAfter": 1200,
        "metaInfo": {"udf1": payment_token, "udf2": merchant_subscription_id},
        "paymentFlow": {
            "type": "SUBSCRIPTION_SETUP",
            "merchantSubscriptionId": merchant_subscription_id,
            "authWorkflowType": "TRANSACTION",
            "amountType": "FIXED",
            "maxAmount": paise,
            "frequency": "MONTHLY",
            "expireAt": int(expire_at_ms),
            "message": message[:100],
            "merchantUrls": {"redirectUrl": redirect_url},
        },
    }
    r = requests.post(_urls()["pg"] + "/checkout/v2/pay", json=body, headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code != 200 or not r.json().get("redirectUrl"):
        raise PhonePeError(f"PhonePe subscription setup failed ({r.status_code}): {r.text[:300]}")
    return r.json()["redirectUrl"]


def subscription_status(merchant_subscription_id: str) -> dict:
    """Return {"state": ACTIVE|PAUSED|CANCELLED|REVOKED|..., "subscription_id": str, "expire_at": int}."""
    r = requests.get(f"{_urls()['pg']}/subscriptions/v2/{merchant_subscription_id}/status",
                     params={"details": "false"}, headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code != 200:
        raise PhonePeError(f"PhonePe subscription status failed ({r.status_code}): {r.text[:300]}")
    d = r.json()
    return {
        "state": d.get("state", ""),
        "subscription_id": d.get("subscriptionId", ""),
        "expire_at": int(d.get("expireAt") or 0),
    }


def notify_redemption(merchant_order_id: str, merchant_subscription_id: str, amount_rupees: int,
                      expire_at_ms: int) -> dict:
    """Send the mandatory 24h pre-debit notification before charging a monthly AutoPay cycle."""
    body = {
        "merchantOrderId": merchant_order_id,
        "amount": int(amount_rupees) * 100,
        "expireAt": int(expire_at_ms),
        "paymentFlow": {
            "type": "SUBSCRIPTION_REDEMPTION",
            "merchantSubscriptionId": merchant_subscription_id,
            "redemptionRetryStrategy": "STANDARD",
            "autoDebit": True,
        },
    }
    r = requests.post(_urls()["pg"] + "/subscriptions/v2/notify", json=body, headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code != 200:
        raise PhonePeError(f"PhonePe notify redemption failed ({r.status_code}): {r.text[:300]}")
    return r.json()


def execute_redemption(merchant_order_id: str, merchant_subscription_id: str, amount_rupees: int) -> dict:
    """Execute the monthly AutoPay debit after the 24h pre-debit notification window."""
    body = {
        "merchantOrderId": merchant_order_id,
        "amount": int(amount_rupees) * 100,
        "paymentFlow": {
            "type": "SUBSCRIPTION_REDEMPTION",
            "merchantSubscriptionId": merchant_subscription_id,
            "redemptionRetryStrategy": "STANDARD",
            "autoDebit": True,
        },
    }
    r = requests.post(_urls()["pg"] + "/subscriptions/v2/redeem", json=body, headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code != 200:
        raise PhonePeError(f"PhonePe execute redemption failed ({r.status_code}): {r.text[:300]}")
    return r.json()


def redemption_order_status(merchant_order_id: str) -> dict:
    """Check the status of a recurring redemption order."""
    r = requests.get(f"{_urls()['pg']}/subscriptions/v2/order/{merchant_order_id}/status",
                     params={"details": "false"}, headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code == 404:
        return order_status(merchant_order_id)
    if r.status_code != 200:
        raise PhonePeError(f"PhonePe redemption status failed ({r.status_code}): {r.text[:300]}")
    d = r.json()
    txn = ""
    for p in d.get("paymentDetails") or []:
        if p.get("state") == "COMPLETED" or not txn:
            txn = p.get("transactionId") or txn
    return {"state": d.get("state", "PENDING"), "amount": int(d.get("amount") or 0), "transaction_id": txn}


def cancel_subscription(merchant_subscription_id: str) -> dict:
    """Cancel an active PhonePe AutoPay mandate."""
    r = requests.post(f"{_urls()['pg']}/subscriptions/v2/{merchant_subscription_id}/cancel",
                      headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code != 200:
        raise PhonePeError(f"PhonePe cancel subscription failed ({r.status_code}): {r.text[:300]}")
    return r.json()


def order_status(merchant_order_id: str) -> dict:
    """Returns {"state": COMPLETED|FAILED|PENDING, "amount": paise, "transaction_id": str, "payment_token": str}."""
    r = requests.get(f"{_urls()['pg']}/checkout/v2/order/{merchant_order_id}/status", params={"details": "false"},
                     headers=_auth_header(), timeout=TIMEOUT)
    if r.status_code != 200:
        raise PhonePeError(f"PhonePe order status failed ({r.status_code}): {r.text[:300]}")
    d = r.json()
    txn = ""
    for p in d.get("paymentDetails") or []:
        if p.get("state") == "COMPLETED" or not txn:
            txn = p.get("transactionId") or txn
    return {"state": d.get("state", "PENDING"), "amount": int(d.get("amount") or 0), "transaction_id": txn,
            "payment_token": (d.get("metaInfo") or {}).get("udf1", "")}


def webhook_authorised(header: str | None) -> bool:
    """True if no webhook credentials are configured (status is re-checked with PhonePe anyway),
    or if the Authorization header equals SHA256(username:password)."""
    user, pw = _env("PHONEPE_WEBHOOK_USER"), _env("PHONEPE_WEBHOOK_PASS")
    if not (user and pw):
        return True
    expected = hashlib.sha256(f"{user}:{pw}".encode()).hexdigest()
    given = (header or "").strip().split(" ")[-1].lower()
    return hmac.compare_digest(given, expected)
