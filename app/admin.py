"""Owner dashboard: read-only view of customers and their WhatsApp chats.

  /admin/                      dashboard page (files in the "astrovinod dashboard" folder)
  /admin/api/customers         all customers with their latest message
  /admin/api/chats/{phone}     one customer's conversation, oldest first

The API needs the header  Authorization: Bearer <ADMIN_PASSWORD>  (set ADMIN_PASSWORD in Render).
Without ADMIN_PASSWORD the API is switched off.
"""
import hmac
import json
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import func, select

from . import bot
from .db import chat_history, customers

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "astrovinod dashboard"
MAX_MESSAGES = 1000  # newest messages returned per chat

router = APIRouter(prefix="/admin/api")


def _check(authorization: str | None) -> None:
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        raise HTTPException(503, "Dashboard is off: set ADMIN_PASSWORD on the server")
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given.encode(), password.encode()):
        raise HTTPException(401, "Wrong password")


def _chart_highlights(raw: str) -> dict:
    try:
        chart = json.loads(raw)
        return {"lagna": chart["lagna"]["sign"], "moon_sign": chart["moon_sign_rashi"],
                "nakshatra": chart["janma_nakshatra"]}
    except Exception:  # noqa: BLE001
        return {}


@router.get("/customers")
def list_customers(authorization: str | None = Header(None)) -> list[dict]:
    _check(authorization)
    stats = (select(chat_history.c.phone_number, func.max(chat_history.c.id).label("last_id"),
                    func.count(chat_history.c.id).label("n"))
             .group_by(chat_history.c.phone_number).subquery())
    q = (select(customers, stats.c.n, chat_history.c.message.label("last_message"),
                chat_history.c.role.label("last_role"), chat_history.c.timestamp.label("last_time"))
         .select_from(customers
                      .outerjoin(stats, stats.c.phone_number == customers.c.phone_number)
                      .outerjoin(chat_history, chat_history.c.id == stats.c.last_id)))
    with bot.store().engine.connect() as conn:
        rows = conn.execute(q).mappings().all()

    out = []
    for r in rows:
        state = r["conversation_state"] or "onboarding"
        out.append({
            "phone": r["phone_number"],
            "name": r["full_name"] or r["profile_name"],
            "profile_name": r["profile_name"],
            "registered": state == "ready",
            "status": state,
            "dob": r["dob"], "tob": r["birth_time"],
            "place": r["resolved_place"] or r["birth_place"],
            "created_at": r["created_at"],
            "last_message": (r["last_message"] or "")[:200],
            "last_role": r["last_role"] or "",
            "last_time": r["last_time"] or r["updated_at"],
            "message_count": r["n"] or 0,
            **_chart_highlights(r["chart_summary"]),
        })
    out.sort(key=lambda c: c["last_time"] or "", reverse=True)
    return out


@router.get("/chats/{phone}")
def get_chat(phone: str, authorization: str | None = Header(None)) -> list[dict]:
    _check(authorization)
    q = (select(chat_history.c.role, chat_history.c.message, chat_history.c.timestamp, chat_history.c.message_type)
         .where(chat_history.c.phone_number == phone)
         .order_by(chat_history.c.id.desc()).limit(MAX_MESSAGES))
    with bot.store().engine.connect() as conn:
        rows = conn.execute(q).mappings().all()
    return [{"role": r["role"], "text": r["message"], "time": r["timestamp"], "type": r["message_type"]}
            for r in reversed(rows)]
