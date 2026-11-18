"""Download all bot data from the database into an Excel file in this folder.

Run:  double-click export_data.bat   (or: .venv\\Scripts\\python.exe export_data.py)
Output: exported_data/AstroVinod_data_<date-time>.xlsx with two sheets: Customers and ChatHistory
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select

from app.db import DbStore, chat_history, customers

OUT_DIR = Path(__file__).resolve().parent / "exported_data"
EXCEL_CELL_LIMIT = 32000

# Readable column order (the long chart data goes last)
CUSTOMER_ORDER = ["phone_number", "full_name", "profile_name", "dob", "birth_time", "birth_place", "resolved_place",
                  "timezone", "latitude", "longitude", "consent", "conversation_state", "created_at", "updated_at",
                  "last_message_id", "lagna", "moon_sign", "nakshatra", "kundli_pdf_notes", "chart_summary"]
HISTORY_ORDER = ["id", "timestamp", "phone_number", "role", "message_type", "message", "message_id"]


def _chart_highlights(raw: str) -> dict:
    try:
        chart = json.loads(raw)
        return {"lagna": chart["lagna"]["sign"], "moon_sign": chart["moon_sign_rashi"],
                "nakshatra": chart["janma_nakshatra"]}
    except Exception:  # noqa: BLE001
        return {}


def _write_sheet(ws, columns: list[str], rows: list[dict], wide: set[str]) -> None:
    head_fill = PatternFill("solid", fgColor="4B2E83")
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
    for r in rows:
        ws.append([str(r.get(c, "") or "")[:EXCEL_CELL_LIMIT] for c in columns])
    for i, col in enumerate(columns, start=1):
        ws.column_dimensions[get_column_letter(i)].width = 60 if col in wide else 20
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=columns[cell.column - 1] in wide)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def main() -> Path:
    store = DbStore()
    with store.engine.connect() as conn:
        cust = [dict(r) for r in conn.execute(select(customers).order_by(customers.c.created_at)).mappings()]
        hist = [dict(r) for r in conn.execute(select(chat_history).order_by(chat_history.c.id)).mappings()]
    for c in cust:
        c.update(_chart_highlights(c.get("chart_summary", "")))

    wb = Workbook()
    ws = wb.active
    ws.title = "Customers"
    _write_sheet(ws, CUSTOMER_ORDER, cust, wide={"kundli_pdf_notes", "chart_summary", "resolved_place"})
    _write_sheet(wb.create_sheet("ChatHistory"), HISTORY_ORDER, hist, wide={"message"})

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"AstroVinod_data_{datetime.now():%Y-%m-%d_%H-%M}.xlsx"
    wb.save(path)
    print(f"Exported {len(cust)} customers and {len(hist)} messages to:\n{path}")
    return path


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print("Export failed:", exc)
        sys.exit(1)
