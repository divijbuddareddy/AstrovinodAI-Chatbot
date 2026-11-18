"""Orchestrates one inbound WhatsApp message end to end."""
import json
import logging
import threading
from collections import defaultdict

from datetime import datetime
from zoneinfo import ZoneInfo

from . import ai, astrology, intents, vedic, whatsapp
from .sheets import open_store
from . import state_machine as sm
from .state_machine import step

log = logging.getLogger("astrovinod")
_store = None
_phone_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_seen_lock = threading.Lock()
_recent_ids: set[str] = set()


def store():
    global _store
    if _store is None:
        _store = open_store()
    return _store


def reply(phone: str, text: str) -> None:
    """Send (chunked) and log every outbound message to ChatHistory."""
    for chunk in whatsapp.split_message(text):
        wa_id = whatsapp.send_text(phone, chunk)
        store().log_message(phone, "assistant", chunk, wa_id, "text")


def handle(msg: dict) -> None:
    phone = msg["phone"]
    mid = msg["message_id"]

    # Meta retries webhooks - drop duplicates (memory first, then the sheet).
    with _seen_lock:
        if mid in _recent_ids:
            return
        _recent_ids.add(mid)
        if len(_recent_ids) > 5000:
            _recent_ids.clear()

    with _phone_locks[phone]:
        try:
            s = store()
            if s.message_seen(mid):
                return

            if not msg["text"]:
                s.log_message(phone, "user", f"[unsupported {msg['type']} message]", mid, msg["type"])
                reply(phone, "🙏 I can read text messages, images and PDF documents. Please send your question as text.")
                return

            logged_text = msg["text"]
            if msg["media_id"]:
                logged_text = f"[{msg['type']}{': ' + msg['filename'] if msg['filename'] else ''}] {msg['text']}"
            s.log_message(phone, "user", logged_text, mid, msg["type"])

            existing = s.get_customer(phone)
            result = step(existing, phone, msg["profile_name"], msg["text"], msg["type"])
            customer = result.customer
            customer["last_message_id"] = mid
            s.upsert_customer(customer)

            if result.reply:
                reply(phone, result.reply)

            if result.action == "onboard":
                onboard(customer, msg)
            elif result.action == "generate_horoscope":
                generate_horoscope(customer)
            elif result.action == "answer_question":
                answer(customer, msg)
        except Exception:
            log.exception("Failed to handle message %s from %s", mid, phone)
            try:
                reply(phone, "🙏 Sorry, something went wrong on my side. Please try again in a few minutes.")
            except Exception:
                log.exception("Also failed to send the error reply")


def ensure_chart(customer: dict, force: bool = False) -> dict:
    """Return the client's natal chart, computing and saving it to the Customers sheet if needed.
    Birth details are never asked again once they are on file."""
    if not force and customer.get("chart_summary"):
        try:
            chart = json.loads(customer["chart_summary"])
            if "lagna" in chart:
                return chart
        except (ValueError, TypeError):
            pass

    if not (customer.get("latitude") and customer.get("longitude")):
        customer.update(astrology.geocode(customer["birth_place"]))
    lat, lon = float(customer["latitude"]), float(customer["longitude"])
    tz_name, iso_dt = astrology.birth_datetime(customer["dob"], customer["birth_time"], lat, lon)
    customer["timezone"] = tz_name

    chart = vedic.natal_chart(customer["dob"], customer["birth_time"], tz_name, lat, lon)
    extras = astrology.prokerala_extras(lat, lon, iso_dt)  # None while Prokerala has no credits
    if extras:
        chart["prokerala"] = extras
    customer["chart_summary"] = json.dumps(chart, ensure_ascii=False, separators=(",", ":"))
    store().upsert_customer(customer)
    return chart


def _tz(customer: dict) -> ZoneInfo:
    return ZoneInfo(customer.get("timezone") or "Asia/Kolkata")


def now_context(customer: dict, chart: dict) -> dict:
    now = datetime.now(_tz(customer))
    return {
        "local_now": now.strftime("%A %d %B %Y, %I:%M %p"),
        "running_dasha": vedic.running_dasha(chart, now.date()),
        "transits_today": vedic.transit_snapshot(chart, now),
    }


_FIELD_PROMPTS = {
    "full_name": "*Full Name:*",
    "dob": "*Date of Birth:* (DD/MM/YYYY)",
    "birth_time": "*Time of Birth:* HH:MM AM/PM",
    "birth_place": "*Place of Birth:* (City, State, Country)",
}


def onboard(customer: dict, msg: dict) -> None:
    """Welcome flow: read birth details from the client's message or uploaded Kundali, ask only for what's missing,
    then build the chart and send the master-prompt analysis."""
    phone = customer["phone_number"]
    media, mime = None, ""
    if msg["media_id"]:
        try:
            media, mime = whatsapp.download_media(msg["media_id"])
            mime = (msg["mime_type"] or mime or "").split(";")[0].strip()
        except Exception:
            log.exception("Media download failed for %s", msg["media_id"])
        if mime not in ("application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"):
            reply(phone, "🙏 Please upload your Kundali as a *PDF* (or a clear photo), or simply type your birth details.")
            return
        reply(phone, "📎 Thank you! Reading your Kundali now…")

    text = "" if media and msg["text"].startswith("Please analyse") else msg["text"]
    last_bot = next((r["message"] for r in reversed(store().recent_history(phone, limit=6))
                     if r.get("role") == "assistant"), "")
    details = ai.extract_birth_details(customer, text, media, mime, last_bot)

    if details.full_name:
        customer["full_name"] = details.full_name.strip()
    if sm.valid_dob(details.date_of_birth):
        customer["dob"] = details.date_of_birth
    if sm.valid_time(details.time_of_birth) and not details.time_is_ambiguous:
        customer["birth_time"] = details.time_of_birth
    if details.place_of_birth and details.place_of_birth != customer.get("birth_place"):
        customer.update(birth_place=details.place_of_birth.strip(), latitude="", longitude="", resolved_place="")
    if details.is_birth_chart and details.chart_notes:
        customer["kundli_pdf_notes"] = details.chart_notes[:20000]

    missing = [k for k in sm.PROFILE_FIELDS if not customer.get(k)]
    if missing:
        customer["conversation_state"] = "onboarding"
        store().upsert_customer(customer)
        first = customer.get("full_name", "").split(" ")[0]
        lines = []
        if details.time_is_ambiguous and "birth_time" in missing:
            lines.append(f"Was your birth time *{details.time_of_birth}* in the morning (AM) or evening (PM)? "
                         "Please reply like 06:35 AM.")
            missing.remove("birth_time")
        if missing:
            got = "Thank you" + (f", {first} ji" if first else "") + "! 🙏"
            if media and not details.is_birth_chart:
                got = "🙏 I couldn't find birth details in that file."
            elif media:
                got = "🙏 Thank you! I've read your Kundali, but I still need a few details."
            lines.insert(0, got + "\n\nPlease share:\n" + "\n".join(_FIELD_PROMPTS[k] for k in missing))
        reply(phone, "\n\n".join(lines))
        return

    customer["consent"] = "yes"
    customer["conversation_state"] = "ready"
    store().upsert_customer(customer)
    reply(phone, (
        f"🙏 Thank you, {customer['full_name'].split(' ')[0]} ji! Your birth profile:\n\n"
        f"• *Name:* {customer['full_name']}\n• *Date of Birth:* {customer['dob']}\n"
        f"• *Time of Birth:* {customer['birth_time']}\n• *Place of Birth:* {customer['birth_place']}\n\n"
        "🔭 Generating your Vedic birth chart and preparing your birth profile. This takes 2-3 minutes…\n"
        "_(Reply RESET anytime to correct your details.)_"))
    generate_horoscope(customer)


def generate_horoscope(customer: dict) -> None:
    phone = customer["phone_number"]
    try:
        chart = ensure_chart(customer, force=True)
    except astrology.BirthplaceNotFound:
        customer.update(conversation_state="onboarding", birth_place="", latitude="", longitude="", resolved_place="")
        store().upsert_customer(customer)
        reply(phone, "I couldn't find that birthplace on the map. Please send it again as *City, Country* (e.g. Mysuru, India).")
        return
    report = ai.horoscope_report(customer, chart, now_context(customer, chart))
    reply(phone, report)


def answer(customer: dict, msg: dict) -> None:
    s = store()
    phone = customer["phone_number"]
    try:
        chart = ensure_chart(customer)
    except astrology.BirthplaceNotFound:
        customer.update(conversation_state="onboarding", birth_place="", latitude="", longitude="", resolved_place="")
        s.upsert_customer(customer)
        reply(phone, "Before I answer, I need to locate your birthplace. Please send it as *City, Country* (e.g. Mysuru, India).")
        return
    now_ctx = now_context(customer, chart)

    history = s.recent_history(phone, limit=20)
    # The current message is the last history row; it is passed separately (with any media).
    if history and history[-1].get("message_id") == msg["message_id"]:
        history = history[:-1]

    intent = None if msg["media_id"] else intents.detect(msg["text"], datetime.now(_tz(customer)).date())
    if intent:
        lat, lon, tz_name = float(customer["latitude"]), float(customer["longitude"]), customer["timezone"]
        period = vedic.period_transits(chart, intent.start, intent.end, tz_name)
        if intent.id == "DAILY_GUIDANCE":
            period["panchang"] = vedic.daily_panchang(intent.start, tz_name, lat, lon)
            period["transits"] = vedic.transit_snapshot(
                chart, datetime(intent.start.year, intent.start.month, intent.start.day, 9, 0, tzinfo=_tz(customer)))
            period["running_dasha_on_date"] = vedic.running_dasha(chart, intent.start)
            period["note"] = "Panchang timings are calculated for the client's birthplace."
        log.info("%s for %s (%s..%s)", intent.id, phone, intent.start, intent.end)
        text = ai.periodic_guidance(customer, chart, now_ctx, intent, period, history, msg["text"])
        reply(phone, text)
        return

    media, mime = None, ""
    if msg["media_id"]:
        try:
            media, mime = whatsapp.download_media(msg["media_id"])
            mime = (msg["mime_type"] or mime or "").split(";")[0].strip()
        except Exception:
            log.exception("Media download failed for %s", msg["media_id"])

    text = ai.answer_question(customer, chart, now_ctx, history, msg["text"], media, mime)
    reply(phone, text)
