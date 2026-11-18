"""Google Sheets is the ONLY data store for this bot.

Tabs (created automatically if missing, missing columns are appended):
  Customers   - one row per WhatsApp number (profile + conversation state)
  ChatHistory - every inbound/outbound message
"""
import json
import threading
from datetime import datetime, timezone

import gspread

from . import config

CUSTOMER_COLS = [
    "phone_number", "profile_name", "full_name", "dob", "birth_time", "birth_place",
    "resolved_place", "latitude", "longitude", "timezone", "consent",
    "conversation_state", "chart_summary", "kundli_pdf_notes", "last_message_id", "created_at", "updated_at",
]
HISTORY_COLS = ["timestamp", "phone_number", "message_id", "role", "message_type", "message"]

# Google Sheets hard limit is 50,000 chars per cell.
MAX_CELL = 49000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class _Tab:
    def __init__(self, book, title: str, cols: list[str]):
        try:
            self.ws = book.worksheet(title)
        except gspread.WorksheetNotFound:
            self.ws = book.add_worksheet(title=title, rows=1000, cols=len(cols))
        header = self.ws.row_values(1)
        if not header:
            header = list(cols)
        missing = [c for c in cols if c not in header]
        header = header + missing
        if self.ws.col_count < len(header):
            self.ws.add_cols(len(header) - self.ws.col_count)
        if missing or not self.ws.row_values(1):
            self.ws.update([header], "A1", value_input_option="RAW")
        self.header = header

    def records(self) -> list[dict]:
        rows = self.ws.get_all_values()
        out = []
        for row in rows[1:]:
            row = row + [""] * (len(self.header) - len(row))
            out.append(dict(zip(self.header, row)))
        return out

    def to_row(self, data: dict) -> list[str]:
        row = []
        for col in self.header:
            v = data.get(col, "")
            v = "" if v is None else str(v)
            row.append(v[:MAX_CELL])
        return row

    def append(self, data: dict) -> None:
        # RAW keeps phone numbers as text and blocks formula injection ("=...").
        self.ws.append_row(self.to_row(data), value_input_option="RAW")

    def update_row(self, row_number: int, data: dict) -> None:
        end = _col_letter(len(self.header))
        self.ws.update([self.to_row(data)], f"A{row_number}:{end}{row_number}", value_input_option="RAW")


class SheetStore:
    def __init__(self):
        if config.GOOGLE_SERVICE_ACCOUNT_JSON:
            gc = gspread.service_account_from_dict(json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON))
        else:
            gc = gspread.service_account(filename=config.GOOGLE_SERVICE_ACCOUNT_FILE)
        book = gc.open_by_key(config.GOOGLE_SHEET_ID)
        self.customers = _Tab(book, "Customers", CUSTOMER_COLS)
        self.history = _Tab(book, "ChatHistory", HISTORY_COLS)
        self._write_lock = threading.Lock()

    # ---------- customers ----------
    def get_customer(self, phone: str) -> dict | None:
        for rec in self.customers.records():
            if _digits(rec.get("phone_number")) == phone:
                return rec
        return None

    def upsert_customer(self, customer: dict) -> None:
        customer = dict(customer)
        customer["updated_at"] = now_iso()
        with self._write_lock:
            for i, rec in enumerate(self.customers.records()):
                if _digits(rec.get("phone_number")) == customer["phone_number"]:
                    merged = {**rec, **customer}
                    self.customers.update_row(i + 2, merged)
                    return
            customer.setdefault("created_at", now_iso())
            self.customers.append(customer)

    # ---------- chat history ----------
    def message_seen(self, message_id: str) -> bool:
        if not message_id:
            return False
        idx = self.history.header.index("message_id") + 1
        return message_id in self.history.ws.col_values(idx)

    def log_message(self, phone: str, role: str, message: str, message_id: str = "", message_type: str = "text") -> None:
        with self._write_lock:
            self.history.append({
                "timestamp": now_iso(),
                "phone_number": phone,
                "message_id": message_id,
                "role": role,
                "message_type": message_type,
                "message": message,
            })

    def recent_history(self, phone: str, limit: int = 20) -> list[dict]:
        rows = [r for r in self.history.records() if _digits(r.get("phone_number")) == phone and r.get("message")]
        return rows[-limit:]


class AppsScriptStore:
    """Same interface as SheetStore, but talks to the Apps Script web app bound to the sheet
    (google_sheet_script/Code.gs). No Google Cloud project or service account needed."""

    def __init__(self):
        import requests
        self._session = requests.Session()
        self._call("setup")

    def _call(self, action: str, **payload):
        resp = self._session.post(
            config.APPS_SCRIPT_URL,
            json={"secret": config.APPS_SCRIPT_SECRET, "action": action, **payload},
            timeout=60,
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError("Google Sheet script did not return JSON - check the deployment is a Web app "
                               f"with access 'Anyone'. Response starts: {resp.text[:200]!r}")
        if not data.get("ok"):
            raise RuntimeError(f"Google Sheet script error ({action}): {data.get('error')}")
        return data.get("result")

    def get_customer(self, phone: str) -> dict | None:
        return self._call("get_customer", phone=phone)

    def upsert_customer(self, customer: dict) -> None:
        customer = {k: ("" if v is None else str(v)) for k, v in customer.items()}
        customer["updated_at"] = now_iso()
        customer.setdefault("created_at", now_iso())
        self._call("upsert_customer", customer=customer)

    def message_seen(self, message_id: str) -> bool:
        return bool(message_id) and bool(self._call("message_seen", message_id=message_id))

    def log_message(self, phone: str, role: str, message: str, message_id: str = "", message_type: str = "text") -> None:
        self._call("log_message", row={
            "timestamp": now_iso(), "phone_number": phone, "message_id": message_id,
            "role": role, "message_type": message_type, "message": message,
        })

    def recent_history(self, phone: str, limit: int = 20) -> list[dict]:
        return self._call("recent_history", phone=phone, limit=limit) or []


def open_store():
    if config.STORAGE != "google_sheet":
        from .db import DbStore
        return DbStore()
    if config.APPS_SCRIPT_URL:
        return AppsScriptStore()
    if config.GOOGLE_SHEET_ID:
        return SheetStore()
    raise RuntimeError("STORAGE=google_sheet but no sheet configured: set APPS_SCRIPT_URL + APPS_SCRIPT_SECRET.")


def _digits(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())
