"""Start the dashboard on this computer with REAL data from the Neon database.

Double-click "Start Dashboard.bat". Keep the black window open while using the dashboard.
Only this computer can open it (127.0.0.1). It does not reply to WhatsApp messages; the live bot on Render does that.
"""
import os
import re
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 8765

key = re.search(r'key:\s*"([^"]+)"', (HERE / "config.js").read_text(encoding="utf-8")).group(1)
os.environ["ADMIN_PASSWORD"] = key
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

threading.Timer(4, lambda: webbrowser.open((HERE / "index.html").as_uri())).start()
print(f"\n  AstroVinod dashboard running. Keep this window open.\n  Close it to stop.\n")
uvicorn.run("main:app", host="127.0.0.1", port=PORT, log_level="warning")
