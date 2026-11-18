import os

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


WHATSAPP_TOKEN = _req("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = _req("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = _req("WHATSAPP_VERIFY_TOKEN")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v22.0")
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()

ANTHROPIC_API_KEY = _req("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

PROKERALA_CLIENT_ID = _req("PROKERALA_CLIENT_ID")
PROKERALA_CLIENT_SECRET = _req("PROKERALA_CLIENT_SECRET")
PROKERALA_AYANAMSA = os.getenv("PROKERALA_AYANAMSA", "1")

NOMINATIM_USER_AGENT = _req("NOMINATIM_USER_AGENT")

# Storage: PostgreSQL via DATABASE_URL (recommended). If empty, a local SQLite file is used.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Optional legacy storage: Google Sheet via Apps Script (google_sheet_script/Code.gs) or service account
STORAGE = os.getenv("STORAGE", "database").strip().lower()  # database | google_sheet
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "").strip()
APPS_SCRIPT_SECRET = os.getenv("APPS_SCRIPT_SECRET", "").strip()

# Option B: Google service account
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
# On hosts without a file system for secrets (e.g. Render), paste the whole JSON key into this variable instead.
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
