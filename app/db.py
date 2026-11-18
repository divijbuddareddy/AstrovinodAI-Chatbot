"""Database storage (PostgreSQL in production, SQLite for local testing).

Default            -> SQLite file astrovinod.db in the project folder.
DATABASE_URL set   -> PostgreSQL instead (optional, e.g. for cloud hosting).

Tables (created automatically):
  customers     - one row per WhatsApp number (profile, conversation state, saved chart)
  chat_history  - every inbound/outbound message
"""
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (Column, Integer, MetaData, String, Table, Text, create_engine, insert, select,
                        update)

from . import config

log = logging.getLogger("astrovinod")
metadata = MetaData()

CUSTOMER_COLS = [
    "profile_name", "full_name", "dob", "birth_time", "birth_place", "resolved_place", "latitude", "longitude",
    "timezone", "consent", "conversation_state", "chart_summary", "kundli_pdf_notes", "last_message_id",
    "created_at", "updated_at",
]

customers = Table(
    "customers", metadata,
    Column("phone_number", String(32), primary_key=True),
    *[Column(c, Text, nullable=False, server_default="") for c in CUSTOMER_COLS],
)

chat_history = Table(
    "chat_history", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", String(40), nullable=False),
    Column("phone_number", String(32), nullable=False, index=True),
    Column("message_id", String(255), nullable=False, server_default="", index=True),
    Column("role", String(16), nullable=False),
    Column("message_type", String(32), nullable=False, server_default="text"),
    Column("message", Text, nullable=False, server_default=""),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _engine_url() -> str:
    url = config.DATABASE_URL
    if not url:
        path = Path(__file__).resolve().parent.parent / "astrovinod.db"
        log.info("Using SQLite database file %s", path)
        return f"sqlite:///{path}"
    # Neon / Render / Heroku style URLs -> SQLAlchemy psycopg3 driver
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _clean(d: dict) -> dict:
    return {k: ("" if v is None else str(v)) for k, v in d.items()}


class DbStore:
    def __init__(self):
        url = _engine_url()
        # Neon's "-pooler" endpoint is PgBouncer in transaction mode: disable server-side prepared statements.
        connect_args = {"prepare_threshold": None} if url.startswith("postgresql") else {}
        self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=300, connect_args=connect_args)
        metadata.create_all(self.engine)
        self._lock = threading.Lock()
        log.info("Database ready (%s)", self.engine.url.get_backend_name())

    # ---------- customers ----------
    def get_customer(self, phone: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(customers).where(customers.c.phone_number == phone)).mappings().first()
        return dict(row) if row else None

    def upsert_customer(self, customer: dict) -> None:
        data = _clean({k: v for k, v in customer.items() if k == "phone_number" or k in CUSTOMER_COLS})
        data["updated_at"] = now_iso()
        with self._lock, self.engine.begin() as conn:
            exists = conn.execute(select(customers.c.phone_number)
                                  .where(customers.c.phone_number == data["phone_number"])).first()
            if exists:
                conn.execute(update(customers).where(customers.c.phone_number == data["phone_number"])
                             .values(**{k: v for k, v in data.items() if k not in ("phone_number", "created_at")}))
            else:
                data.setdefault("created_at", now_iso())
                if not data["created_at"]:
                    data["created_at"] = now_iso()
                conn.execute(insert(customers).values(**data))

    # ---------- chat history ----------
    def message_seen(self, message_id: str) -> bool:
        if not message_id:
            return False
        with self.engine.connect() as conn:
            return conn.execute(select(chat_history.c.id)
                                .where(chat_history.c.message_id == message_id).limit(1)).first() is not None

    def log_message(self, phone: str, role: str, message: str, message_id: str = "", message_type: str = "text") -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(chat_history).values(
                timestamp=now_iso(), phone_number=phone, message_id=message_id or "",
                role=role, message_type=message_type or "text", message=message or "",
            ))

    def recent_history(self, phone: str, limit: int = 20) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(chat_history).where(chat_history.c.phone_number == phone)
                .order_by(chat_history.c.id.desc()).limit(limit)
            ).mappings().all()
        return [dict(r) for r in reversed(rows) if r["message"]]
