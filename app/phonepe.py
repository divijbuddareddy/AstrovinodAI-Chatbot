"""PhonePe Payment Gateway - Standard Checkout v2 (plain HTTPS, no SDK).

Render settings:
  PHONEPE_CLIENT_ID, PHONEPE_CLIENT_SECRET, PHONEPE_CLIENT_VERSION   from PhonePe Business > Developer Settings > API Keys
  PHONEPE_ENV                    production (default) | sandbox
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
