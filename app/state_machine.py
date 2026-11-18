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

🌟 Let's begin by setting up your birth profile.

*Step 1:* Do you have a copy of your birth chart (Kundali)?

📎 *If YES:* Please upload your birth chart in PDF format. I will use it as the reference for your astrological analysis.

📝 *If NO:* No problem! I can generate your birth chart using your birth details.
Please share the following information:
*Full Name:*
*Date of Birth:* (DD/MM/YYYY)
*Time of Birth:* HH:MM AM/PM
*Place of Birth:* (City, State, Country)

🔭 Once I receive your details, I will generate your Vedic birth chart using precise astrological calculations and prepare your birth profile.

Let's begin your journey of cosmic insights! ✨"""

ASK_PDF = "📎 Wonderful! Please upload your birth chart (Kundali) here in *PDF format*. I will use it as the reference for your astrological analysis."

ASK_DETAILS = """📝 No problem! I can generate your birth chart using your birth details.
Please share the following information:

*Full Name:*
*Date of Birth:* (DD/MM/YYYY)
*Time of Birth:* HH:MM AM/PM
*Place of Birth:* (City, State, Country)"""

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
        # First message already is a Kundali or contains birth details -> process it straight away.
        if is_media or re.search(r"\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{4}", msg):
            return StepResult(c, "", action="onboard")
        return StepResult(c, WELCOME)

    state = c.get("conversation_state") or "onboarding"

    if RESET_CMD.match(msg):
        for k in PROFILE_FIELDS + CHART_FIELDS + ("consent",):
            c[k] = ""
        c["conversation_state"] = "onboarding"
        return StepResult(c, "Sure, let's set up your birth profile again. 🙏\n\n" + ASK_DETAILS +
                          "\n\nOr upload your Kundali PDF if you have one.")

    if state in LEGACY_ONBOARDING:
        state = c["conversation_state"] = "onboarding"

    if state == "onboarding":
        if is_media:
            return StepResult(c, "", action="onboard")
        if not msg or GREETING.match(msg):
            return StepResult(c, WELCOME)
        if YES.match(msg):
            return StepResult(c, ASK_PDF)
        if NO.match(msg):
            return StepResult(c, ASK_DETAILS)
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
