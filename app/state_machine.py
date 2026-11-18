"""Conversation state machine.

Flow (from the client's "1. Welcome message.docx"):
  new user  -> WELCOME (asks: do you have a Kundali PDF? if yes upload it, if no share details)
  onboarding -> client uploads a Kundali PDF/image, or sends Name / DOB / Time / Place (in one or several messages).
               The bot (bot.onboard) reads the details with Claude, asks only for what is missing,
               then generates the chart and the master-prompt report.
  ready      -> questions, daily/weekly/monthly guidance, chart images/PDFs.

Rows created by the old n8n workflow (collect_name ... confirm_horoscope) keep working.
"""
import re
from dataclasses import dataclass, field
from datetime import date

YES = re.compile(r"^(yes|y|yeah|yep|haan|ha|han|ji|ok|okay|sure|i have|i do|yes i have( it)?)[.! ]*$", re.I)
NO = re.compile(r"^(no|n|nahi|nope|no i don'?t|i don'?t( have( it)?)?|not now|later|cancel)[.! ]*$", re.I)
GREETING = re.compile(r"^(hi+|hello|hey|start|namaste|namaskar|hii+|good (morning|afternoon|evening))[.! ]*$", re.I)
HOROSCOPE_CMD = re.compile(
    r"^(please\s+)?((generate|create|make|send|show|get)\s+)?(me\s+)?(my\s+)?(full\s+)?"
    r"(horoscope|kundli|kundali|birth\s*chart|chart analysis)(\s+report)?(\s+please)?[.! ]*$", re.I)
RESET_CMD = re.compile(r"^(reset|restart|change (my )?details|update (my )?details|new profile)[.! ]*$", re.I)

WELCOME = """🙏 *Welcome to ASTROVINOD AI*
_Your Personal Astrologer._

I'm happy to assist you with your astrological questions and provide personalised insights based on Vedic Astrology.

🌟 Let's begin by setting up your birth profile. I'll ask you 4 quick details: your name, date of birth, time of birth and place of birth.

🔭 Once I receive your details, I will generate your Vedic birth chart using precise astrological calculations and prepare your birth profile.

👉 *May I know your Full Name?*"""

# One question at a time, in this order.
QUESTIONS = {
    "full_name": "👉 *May I know your Full Name?*",
    "dob": "📅 Please share your *Date of Birth* (DD/MM/YYYY)\n_Example: 14/05/1992_",
    "birth_time": "⏰ What is your *Time of Birth*? (HH:MM AM/PM)\n_Example: 06:35 AM_",
    "birth_place": "📍 What is your *Place of Birth*? (City, State, Country)\n_Example: Mysuru, Karnataka, India_",
}

PROFILE_FIELDS = ("full_name", "dob", "birth_time", "birth_place")
CHART_FIELDS = ("resolved_place", "latitude", "longitude", "timezone", "chart_summary", "kundli_pdf_notes")
LEGACY_ONBOARDING = {"collect_name", "collect_dob", "collect_birth_time", "collect_birth_place"}


@dataclass
class StepResult:
    customer: dict
    reply: str = ""
    action: str = "reply"  # reply | onboard | generate_horoscope | answer_question
    extra: dict = field(default_factory=dict)


def has_details(c: dict) -> bool:
    return all(c.get(k) for k in PROFILE_FIELDS)


def step(existing: dict | None, phone: str, profile_name: str, text: str, msg_type: str) -> StepResult:
    c = dict(existing or {})
    c["phone_number"] = phone
    if profile_name:
        c["profile_name"] = profile_name
    msg = text.strip()
    is_media = msg_type in ("image", "document")

    if not existing:
        c["conversation_state"] = "onboarding"
        # A Kundali file as the very first message -> read it straight away.
        if is_media:
            return StepResult(c, "", action="onboard")
        return StepResult(c, WELCOME)

    state = c.get("conversation_state") or "onboarding"

    if RESET_CMD.match(msg):
        for k in PROFILE_FIELDS + CHART_FIELDS + ("consent",):
            c[k] = ""
        c["conversation_state"] = "onboarding"
        return StepResult(c, "Sure, let's set up your birth profile again. 🙏\n\n" + QUESTIONS["full_name"])

    if state in LEGACY_ONBOARDING:
        state = c["conversation_state"] = "onboarding"

    if state == "onboarding":
        if is_media:
            return StepResult(c, "", action="onboard")
        if not msg or GREETING.match(msg):
            nxt = next_question(c)
            return StepResult(c, WELCOME if nxt == "full_name" else "🙏 Let's continue.\n\n" + QUESTIONS[nxt])
        return StepResult(c, "", action="onboard")

    if state == "confirm_horoscope":  # legacy n8n state
        if YES.match(msg) or HOROSCOPE_CMD.match(msg):
            c["consent"] = "yes"
            c["conversation_state"] = "ready"
            return StepResult(c, "🔭 Generating your Vedic birth chart and preparing your birth profile. This takes 2-3 minutes…",
                              action="generate_horoscope")
        c["conversation_state"] = "ready"
        state = "ready"

    if state == "ready":
        if not has_details(c):
            c["conversation_state"] = "onboarding"
            return StepResult(c, WELCOME)
        if HOROSCOPE_CMD.match(msg):
            c["consent"] = "yes"
            return StepResult(c, "🔭 Preparing your complete birth chart analysis. This takes 2-3 minutes…",
                              action="generate_horoscope")
        if GREETING.match(msg):
            return StepResult(c, f"🙏 Welcome back, {c.get('full_name', '').split(' ')[0]} ji!\n\n"
                                 "Ask me any astrology question, ask for your *daily*, *weekly* or *monthly* guidance, "
                                 "or share a chart image/PDF.")
        return StepResult(c, "", action="answer_question")

    c["conversation_state"] = "onboarding"
    return StepResult(c, WELCOME)


def valid_dob(iso: str) -> bool:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return False
    return 1900 <= d.year and d <= date.today()


def valid_time(hhmm: str) -> bool:
    m = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", hhmm or "")
    return bool(m)


def next_question(c: dict) -> str | None:
    """The first profile field still missing, in the order name -> DOB -> time -> place."""
    return next((k for k in PROFILE_FIELDS if not c.get(k)), None)


_NAME_PREFIX = re.compile(r"^(hi|hello|namaste)?[,! ]*(my name is|my name's|i am|i'm|this is|name\s*[:\-]?)\s*", re.I)
_NOT_A_NAME = re.compile(r"^(yes|no|ok|okay|hi|hello|hey|namaste|thanks|thank you|sure|hmm+|na|nahi)[.! ]*$", re.I)


def parse_name(text: str) -> str | None:
    name = _NAME_PREFIX.sub("", text.strip()).strip(" .,!")
    if not name or _NOT_A_NAME.match(name) or re.search(r"\d", name) or not 2 <= len(name) <= 60 or len(name.split()) > 6:
        return None
    return name.title() if name.islower() or name.isupper() else name


def parse_dob(text: str) -> str | None:
    m = re.match(r"^\s*(\d{1,2})\s*[/.\- ]\s*(\d{1,2})\s*[/.\- ]\s*(\d{4})\s*$", text)
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        iso = date(y, mo, d).isoformat()
    except ValueError:
        return None
    return iso if valid_dob(iso) else None


def parse_time(text: str) -> tuple[str | None, bool]:
    """Returns (HH:MM 24h or None, needs_am_pm)."""
    t = text.strip().lower().replace(".", ":").replace(" ", "")
    t = t.replace("a:m:", "am").replace("p:m:", "pm").replace("a:m", "am").replace("p:m", "pm")
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)$", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if not 1 <= h <= 12 or mi > 59:
            return None, False
        if m.group(3) == "pm" and h != 12:
            h += 12
        if m.group(3) == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mi:02d}", False
    m = re.match(r"^(\d{1,2}):(\d{2})(hrs|hours|h)?$", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 23 or mi > 59:
            return None, False
        if 1 <= h <= 12 and not m.group(3):
            return f"{h:02d}:{mi:02d}", True  # could be AM or PM
        return f"{h:02d}:{mi:02d}", False
    return None, False
