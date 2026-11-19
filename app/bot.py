"""Orchestrates one inbound WhatsApp message end to end."""
import json
import logging
import threading
from collections import defaultdict

import re
from datetime import date, datetime
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


def _first(customer: dict) -> str:
    return (customer.get("full_name") or "").split(" ")[0]


def _set_place(customer: dict, place: str) -> bool:
    """Validate a birthplace on the map. Saves it with coordinates; False if not found."""
    try:
        found = astrology.geocode(place)
    except (astrology.BirthplaceNotFound, astrology.GeocodingUnavailable):
        return False
    customer.update(birth_place=place.strip(), **found)
    return True


def onboard(customer: dict, msg: dict) -> None:
    """Collect birth details one question at a time: name -> DOB -> time -> place.
    Each answer is read with a fast parser first; anything unusual (several details in one message,
    "14th May 1992", "evening 6:30", a Kundali PDF) is read by Claude. Then the next missing detail is asked."""
    phone = customer["phone_number"]
    current = sm.next_question(customer)
    text = msg["text"].strip()
    ask_ampm = ""
    place_error = False

    if msg["media_id"]:  # uploaded Kundali PDF / photo
        media, mime = None, ""
        try:
            media, mime = whatsapp.download_media(msg["media_id"])
            mime = (msg["mime_type"] or mime or "").split(";")[0].strip()
        except Exception:
            log.exception("Media download failed for %s", msg["media_id"])
        if mime not in ("application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"):
            reply(phone, "🙏 I can read a Kundali as a *PDF* or a clear photo. Or simply answer:\n\n" + sm.QUESTIONS[current or "full_name"])
            return
        reply(phone, "📎 Thank you! Reading your Kundali now…")
        caption = "" if text.startswith("Please analyse") else text
        details = ai.extract_birth_details(customer, caption, media, mime, sm.QUESTIONS.get(current, ""))
        _merge(customer, details)
        if details.is_birth_chart and details.chart_notes:
            customer["kundli_pdf_notes"] = details.chart_notes[:20000]
        elif not details.is_birth_chart:
            reply(phone, "🙏 I couldn't find birth details in that file, so let's do it step by step.")
    else:
        handled = False
        if current == "full_name":
            name = sm.parse_name(text)
            if name:
                customer["full_name"], handled = name, True
        elif current == "dob":
            dob = sm.parse_dob(text)
            if dob:
                customer["dob"], handled = dob, True
        elif current == "birth_time":
            t, ambiguous = sm.parse_time(text)
            if t and not ambiguous:
                customer["birth_time"], handled = t, True
            elif t and ambiguous:
                ask_ampm, handled = t, True
        elif current == "birth_place":
            if 2 <= len(text) <= 120 and not re.search(r"\d{3,}", text):
                handled = True
                if not _set_place(customer, text):
                    place_error = True

        if not handled:  # unusual format or several details at once -> let Claude read it
            last_bot = next((r["message"] for r in reversed(store().recent_history(phone, limit=6))
                             if r.get("role") == "assistant"), "")
            details = ai.extract_birth_details(customer, text, last_bot_message=last_bot)
            _merge(customer, details)
            if details.time_is_ambiguous and details.time_of_birth and not customer.get("birth_time"):
                ask_ampm = details.time_of_birth

    # A place read by Claude (from text or a Kundali) still needs checking on the map.
    if customer.get("birth_place") and not customer.get("latitude") and not place_error:
        if not _set_place(customer, customer["birth_place"]):
            customer["birth_place"] = ""
            place_error = True

    nxt = sm.next_question(customer)
    if nxt:
        customer["conversation_state"] = "onboarding"
        store().upsert_customer(customer)
        if ask_ampm:
            reply(phone, f"Is your birth time *{ask_ampm}* in the morning or evening?\nPlease reply like *{ask_ampm} AM* or *{ask_ampm} PM*.")
        elif place_error:
            reply(phone, "🙏 I couldn't find that place on the map. Please send it as *City, State, Country*\n_Example: Mysuru, Karnataka, India_")
        elif nxt == current:  # the answer couldn't be understood -> ask the same question again
            hints = {"full_name": "Please type your full name.",
                     "dob": "Please send your date of birth like *14/05/1992*.",
                     "birth_time": "Please send your time of birth like *06:35 AM* or *06:35 PM*.",
                     "birth_place": "Please send your place of birth like *Mysuru, Karnataka, India*."}
            reply(phone, "🙏 " + hints[nxt])
        else:
            thanks = f"Thank you, {_first(customer)} ji! 🙏\n\n" if current == "full_name" and _first(customer) else "Thank you! 🙏\n\n"
            reply(phone, thanks + sm.QUESTIONS[nxt])
        return

    customer["consent"] = "yes"
    customer["conversation_state"] = "ready"
    store().upsert_customer(customer)
    reply(phone, (
        f"🙏 Thank you, {_first(customer)} ji! Your birth profile:\n\n"
        f"• *Name:* {customer['full_name']}\n• *Date of Birth:* {_fmt_dob(customer['dob'])}\n"
        f"• *Time of Birth:* {_fmt_time(customer['birth_time'])}\n• *Place of Birth:* {customer['birth_place']}\n\n"
        "🔭 Generating your Vedic birth chart and personalised horoscope. This takes 2-3 minutes…\n"
        "_(Reply RESET anytime to correct your details.)_"))
    generate_horoscope(customer)


def _merge(customer: dict, details) -> None:
    if details.full_name and not customer.get("full_name"):
        customer["full_name"] = details.full_name.strip()
    if sm.valid_dob(details.date_of_birth) and not customer.get("dob"):
        customer["dob"] = details.date_of_birth
    if sm.valid_time(details.time_of_birth) and not details.time_is_ambiguous and not customer.get("birth_time"):
        customer["birth_time"] = details.time_of_birth
    if details.place_of_birth and not customer.get("birth_place"):
        customer.update(birth_place=details.place_of_birth.strip(), latitude="", longitude="", resolved_place="")


def _fmt_dob(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _fmt_time(hhmm: str) -> str:
    try:
        return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p")
    except ValueError:
        return hhmm


def generate_horoscope(customer: dict) -> None:
    phone = customer["phone_number"]
    try:
        chart = ensure_chart(customer, force=True)
    except astrology.BirthplaceNotFound:
        customer.update(conversation_state="onboarding", birth_place="", latitude="", longitude="", resolved_place="")
        store().upsert_customer(customer)
        reply(phone, "🙏 I couldn't find your birthplace on the map. " + sm.QUESTIONS["birth_place"])
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
