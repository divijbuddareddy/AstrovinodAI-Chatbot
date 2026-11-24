"""Orchestrates one inbound WhatsApp message end to end."""
import copy
import json
import logging
import threading
import time
from collections import defaultdict

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import ai, astrology, i18n, intents, plans, vedic, whatsapp
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


_tls = threading.local()  # per-thread: has this attempt already sent a real answer?

# Clients never see "something went wrong". A failed step is retried quietly; if it still fails, the client
# gets a calm holding message and the bot tries once more by itself a few minutes later.
RETRY_DELAYS = (5, 20, 60)
LATER_DELAY = 240
HOLDING_MSG = ("🙏 I'm studying your chart carefully, the planetary calculations need a few more minutes. "
               "I'll send you my answer shortly.")
RESEND_MSG = "🙏 Thank you for your patience. Could you please send your last message once more? I'll reply right away."


class _GaveUp(Exception):
    """A step failed after all its quiet retries."""


def reply(phone: str, text: str, progress: bool = False) -> None:
    """Send (chunked) and log every outbound message to ChatHistory.
    progress=True marks status lines ("Generating…") that are safe to send again if a step is retried."""
    for chunk in whatsapp.split_message(text):
        wa_id = whatsapp.send_text(phone, chunk)
        store().log_message(phone, "assistant", chunk, wa_id, "text")
    if not progress:
        _tls.sent = True


def _with_retries(fn, customer: dict, *args) -> None:
    """Run fn(customer, *args); on failure wait and retry from the same starting point.
    Stops retrying once part of a real answer went out (repeating it would send duplicates)."""
    snapshot = copy.deepcopy(customer)
    for attempt, delay in enumerate((0, *RETRY_DELAYS)):
        if delay:
            time.sleep(delay)
        _tls.sent, _tls.attempt = False, attempt
        try:
            fn(copy.deepcopy(snapshot) if attempt else customer, *args)
            return
        except _GaveUp:
            raise
        except Exception as exc:
            log.exception("%s failed for %s (attempt %d)", fn.__name__, customer.get("phone_number"), attempt + 1)
            if _tls.sent:
                raise _GaveUp from exc
    raise _GaveUp


def _try_later(phone: str, fn, msg: dict | None) -> None:
    """One more automatic attempt a few minutes later, with the latest saved profile."""
    def run():
        with _phone_locks[phone]:
            try:
                customer = store().get_customer(phone)
                if customer:
                    _with_retries(fn, customer, *((msg,) if msg else ()))
                    return
            except Exception:
                log.exception("Delayed retry of %s failed for %s", fn.__name__, phone)
            try:
                reply(phone, RESEND_MSG)
            except Exception:
                log.exception("Could not send the resend request to %s", phone)
    threading.Timer(LATER_DELAY, run).start()


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
        notified = False
        try:
            s = store()
            if s.message_seen(mid):
                return

            if msg["type"] == "reaction":
                handle_reaction(msg)
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
            was_ready = (existing or {}).get("conversation_state") == "ready"

            # Subscription commands (PLANS / GOLD / PLATINUM / VIP) - never counted as chats.
            if was_ready and not msg["media_id"]:
                plan_reply = plans.command_reply(existing, msg["text"])
                if plan_reply:
                    reply(phone, plan_reply)
                    return

            result = step(existing, phone, msg["profile_name"], msg["text"], msg["type"])
            customer = result.customer
            customer["last_message_id"] = mid
            s.upsert_customer(customer)

            # A question after setup counts as one chat; when the plan's chats are used up, show the plans instead.
            counted = result.action == "answer_question" or (result.action == "generate_horoscope" and was_ready)
            if counted:
                blocked = plans.limit_message(customer)
                if blocked:
                    reply(phone, blocked)
                    return

            if result.reply:
                reply(phone, result.reply)
            if result.action == "intro":
                send_intro(phone)
                return
            if result.action in ("language_menu", "language_menu_image"):
                send_language_menu(phone, with_image=result.action == "language_menu_image")
                return

            actions = {"onboard": (onboard, (msg,)), "finish_onboarding": (finish_onboarding, ()),
                       "generate_horoscope": (generate_horoscope, ()), "answer_question": (answer, (msg,))}
            if result.action in actions:
                fn, args = actions[result.action]
                _tls.sent = False
                try:
                    _with_retries(fn, customer, *args)
                except Exception:
                    notified = True
                    if result.action == "onboard":
                        reply(phone, RESEND_MSG)  # details may have half-changed: ask for the same message again
                    else:  # chart reading / answer: hold on and try once more by ourselves
                        reply(phone, HOLDING_MSG, progress=True)
                        _try_later(phone, generate_horoscope if result.action == "finish_onboarding" else fn,
                                   msg if args else None)
                    raise
                if counted:
                    try:
                        note = plans.use_chat(phone)
                        if note:
                            reply(phone, note)
                    except Exception:
                        log.exception("Could not count the chat for %s", phone)
        except Exception:
            log.exception("Failed to handle message %s from %s", mid, phone)
            if not notified:
                try:
                    reply(phone, RESEND_MSG)
                except Exception:
                    log.exception("Could not send the resend request to %s", phone)


# ---------------------------------------------------------------- welcome images + language menu
INTRO_GAP = 2.5  # seconds between messages, so WhatsApp shows them in order (images arrive slower than text)


# Seconds to wait AFTER each image, so the client can look at it before the next one arrives.
IMAGE_PAUSE = {"static/welcome2.jpg": 6, "static/instructions.jpg": 10, "static/language.jpg": 3}


def _send_image(phone: str, path: str) -> None:
    try:
        wa_id = whatsapp.send_image(phone, f"{plans.public_url()}/{path}")
        store().log_message(phone, "assistant", f"[image: {path.rsplit('/', 1)[-1]}]", wa_id, "image")
        time.sleep(IMAGE_PAUSE.get(path, INTRO_GAP))
    except Exception:
        log.exception("Image %s failed for %s", path, phone)  # never block the sign-up on an image


def send_intro(phone: str) -> None:
    """New client (or RESET): welcome image, general instructions image, language image, then the tap menu."""
    for path in i18n.INTRO_IMAGES:
        _send_image(phone, path)
    send_language_menu(phone, with_image=True)


def send_language_menu(phone: str, with_image: bool = False) -> None:
    """Tap-to-choose language list (falls back to a numbered text menu if WhatsApp rejects the list)."""
    show_image = bool(with_image and i18n.LANGUAGE_IMAGE)
    if show_image:
        _send_image(phone, i18n.LANGUAGE_IMAGE)
    body = i18n.MENU_BODY_UNDER_IMAGE if show_image else i18n.MENU_BODY
    rows = [(f"lang_{name.lower()}", name if nat == name else f"{name} / {nat}") for name, nat in i18n.MENU_LANGS]
    try:
        wa_id = whatsapp.send_list(phone, body, i18n.MENU_BUTTON, rows)
        store().log_message(phone, "assistant", body + "\n[language menu]", wa_id, "interactive")
    except Exception:
        log.exception("Language list failed for %s - sending the text menu", phone)
        reply(phone, i18n.MENU_TEXT_FALLBACK)


# ---------------------------------------------------------------- emoji reactions
# A client can long-press one of our messages and react with an emoji. Positive reactions get a short thank-you
# (no AI, not counted as a chat); worried/sad ones get a short caring reply from the AI about that message
# (counted as one chat); anything else - and removing a reaction - is ignored quietly.
POSITIVE_REACTIONS = set("👍❤🙏😊🥰😍👏🙌💯✅🔥😀😃😄😁🤩💙💚💛🧡💜🤍♥👌🤗😇☺🌹💐⭐🌟✨🫶")
CONCERN_REACTIONS = set("😟😢😭😥😰😨😞😔😩😫💔🙁☹😓😣😖🥺😧😦😿😕")
THANKS_GAP = 600  # seconds: at most one thank-you per client every 10 minutes
_last_thanks: dict[str, float] = {}

THANK_YOU = {
    "english": "Thank you", "hindi": "धन्यवाद", "hinglish": "Dhanyavaad", "kannada": "ಧನ್ಯವಾದಗಳು",
    "telugu": "ధన్యవాదాలు", "tamil": "நன்றி", "malayalam": "നന്ദി", "marathi": "धन्यवाद", "bengali": "ধন্যবাদ",
    "gujarati": "આભાર", "punjabi": "ਧੰਨਵਾਦ", "odia": "ଧନ୍ୟବାଦ", "urdu": "شکریہ", "assamese": "ধন্যবাদ",
    "nepali": "धन्यवाद", "sanskrit": "धन्यवादः", "konkani": "देव बरें करूं",
}


def _base_emoji(emoji: str) -> str:
    """Strip skin tones / variation selectors so 👍🏽 and ❤️ match 👍 and ❤."""
    return "".join(ch for ch in emoji if not (0x1F3FB <= ord(ch) <= 0x1F3FF or ord(ch) in (0xFE0F, 0x200D)))


def handle_reaction(msg: dict) -> None:
    s = store()
    phone, emoji = msg["phone"], (msg.get("emoji") or "").strip()
    if not emoji:  # reaction removed
        return
    s.log_message(phone, "user", f"[reaction {emoji}]", msg["message_id"], "reaction")
    customer = s.get_customer(phone)
    if not customer or customer.get("conversation_state") != "ready":
        return  # don't interrupt registration
    base = _base_emoji(emoji)
    first = _first(customer)

    if base and all(ch in POSITIVE_REACTIONS for ch in base):
        now = time.time()
        if now - _last_thanks.get(phone, 0) < THANKS_GAP:
            return
        _last_thanks[phone] = now
        word = THANK_YOU.get((customer.get("language") or "").strip().lower(), "Thank you")
        reply(phone, f"🙏 {word}{', ' + first + ' ji' if first else ''}!")
        return

    if not (base and any(ch in CONCERN_REACTIONS for ch in base)):
        return  # 😂 🤔 😮 etc.: nothing to say

    # Worried / sad: a short caring answer about the message they reacted to (uses the AI -> counts as a chat).
    blocked = plans.limit_message(customer)
    if blocked:
        reply(phone, blocked)
        return
    reacted = next((r["message"] for r in s.recent_history(phone, limit=40)
                    if r.get("message_id") == msg.get("reacted_to")), "")
    note = (f"[The client reacted with {emoji} to this message of yours: \"{reacted[:700]}\"]" if reacted
            else f"[The client reacted with {emoji} to one of your recent messages.]")
    question = (note + "\nThey seem worried or sad about it. Reply briefly (2-5 lines): acknowledge the feeling, reassure "
                "them honestly about that specific point using their chart (difficult phases pass, what helps), and "
                "invite them to tell you what is worrying them.")
    _tls.sent = False
    try:
        _with_retries(answer, customer, {**msg, "text": question, "media_id": ""})
    except Exception:
        log.exception("Reaction reply failed for %s", phone)
        return
    try:
        note = plans.use_chat(phone)
        if note:
            reply(phone, note)
    except Exception:
        log.exception("Could not count the chat for %s", phone)


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
    lang = customer.get("language", "")
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
            reply(phone, i18n.t("kundli_format", lang) + "\n\n" + i18n.question(current or "full_name", lang))
            return
        if not getattr(_tls, "attempt", 0):  # don't repeat it on a quiet retry
            reply(phone, i18n.t("kundli_reading", lang), progress=True)
        caption = "" if text.startswith("Please analyse") else text
        details = ai.extract_birth_details(customer, caption, media, mime, sm.QUESTIONS.get(current, ""))
        _merge(customer, details)
        if details.is_birth_chart and details.chart_notes:
            customer["kundli_pdf_notes"] = details.chart_notes[:20000]
        elif not details.is_birth_chart:
            reply(phone, i18n.t("kundli_none", lang))
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
            reply(phone, i18n.t("ampm", lang, t=ask_ampm))
        elif place_error:
            reply(phone, i18n.t("place_error", lang))
        elif nxt == current:  # the answer couldn't be understood -> ask the same question again
            reply(phone, i18n.hint(nxt, lang))
        else:
            thanks = (i18n.t("thanks_name", lang, first=_first(customer)) if current == "full_name" and _first(customer)
                      else i18n.t("thanks", lang))
            reply(phone, thanks + "\n\n" + i18n.question(nxt, lang))
        return

    # All four details are in: let the client check the place we found before making the chart.
    customer["conversation_state"] = "confirm_place"
    store().upsert_customer(customer)
    reply(phone, sm.place_confirmation(customer))


def finish_onboarding(customer: dict) -> None:
    """Client confirmed the birthplace: show the profile, then make the chart and the full reading."""
    phone = customer["phone_number"]
    customer["consent"] = "yes"
    customer["conversation_state"] = "ready"
    store().upsert_customer(customer)
    lang = customer.get("language", "")
    tr = lambda key, **kw: i18n.t(key, lang, **kw)  # noqa: E731
    reply(phone, (
        f"{tr('profile_head', first=_first(customer))}\n\n"
        f"• *{tr('l_name')}:* {customer['full_name']}\n• *{tr('l_dob')}:* {_fmt_dob(customer['dob'])}\n"
        f"• *{tr('l_tob')}:* {_fmt_time(customer['birth_time'])}\n"
        f"• *{tr('l_pob')}:* {customer.get('resolved_place') or customer['birth_place']}\n\n"
        f"{tr('generating')}\n{tr('reset_hint')}"), progress=True)
    _with_retries(generate_horoscope, customer)


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
        reply(phone, i18n.t("place_not_found", customer.get("language")) + i18n.question("birth_place", customer.get("language")))
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
        reply(phone, i18n.t("place_not_found", customer.get("language")) + i18n.question("birth_place", customer.get("language")))
        return
    now_ctx = now_context(customer, chart)

    history = s.recent_history(phone, limit=20)
    # The current message is the last history row; it is passed separately (with any media).
    if history and history[-1].get("message_id") == msg["message_id"]:
        history = history[:-1]

    intent = None if (msg["media_id"] or msg.get("type") == "reaction") else intents.detect(msg["text"], datetime.now(_tz(customer)).date())
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
