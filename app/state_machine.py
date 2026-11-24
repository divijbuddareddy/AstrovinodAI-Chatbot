"""Conversation state machine.

Flow (from the client's "1. Welcome message.docx"):
  new user  -> WELCOME (asks: do you have a Kundali PDF? if yes upload it, if no share details)
  onboarding -> client uploads a Kundali PDF/image, or sends Name / DOB / Time / Place (in one or several messages).
               The bot (bot.onboard) reads the details with Claude and asks only for what is missing.
  confirm_place -> client confirms the birthplace found on the map (YES), or sends the correct one;
               then the chart and the master-prompt report are generated.
  ready      -> questions, daily/weekly/monthly guidance, chart images/PDFs.

Rows created by the old n8n workflow (collect_name ... confirm_horoscope) keep working.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from . import i18n

YES = re.compile(r"^(yes|y|yeah|yep|haan|ha|han|ji|ok|okay|sure|i have|i do|yes i have( it)?)[.! ]*$", re.I)
NO = re.compile(r"^(no|n|nahi|nope|no i don'?t|i don'?t( have( it)?)?|not now|later|cancel)[.! ]*$", re.I)
GREETING = re.compile(r"^(hi+|hello|hey|hai|hlo|helo|start|namaste|namaskar|namaskara|hii+|good (morning|afternoon|evening)|"
                      r"ನಮಸ್ಕಾರ|ನಮಸ್ತೆ|నమస్కారం|నమస్తే|नमस्ते|नमस्कार|வணக்கம்|നമസ്കാരം|নমস্কার|નમસ્તે|ਸਤ ਸ੍ਰੀ ਅਕਾਲ)[.!🙏 ]*$", re.I)
HOROSCOPE_CMD = re.compile(
    r"^(please\s+)?((generate|create|make|send|show|get)\s+)?(me\s+)?(my\s+)?(full\s+)?"
    r"(horoscope|kundli|kundali|birth\s*chart|chart analysis)(\s+report)?(\s+please)?[.! ]*$", re.I)
CONFIRM_YES = re.compile(
    r"^(yes|y|ya|yah|yeah|yep|yup|yes sir|ok|okay|okk|k|correct|right|perfect|sahi|haan|han|ha|ji|ji haan|s|👍|houdu|avunu|"
    r"ಹೌದು|ಸರಿ|అవును|సరే|हाँ|हां|हा|हो|होय|जी|सही|ஆம்|சரி|അതെ|ശരി|হ্যাঁ|হ্যা|ঠিক|હા|હાં|બરાબર|ਹਾਂ|ਹਾਂਜੀ|ਸਹੀ)"
    r"( (it is|it'?s|its|that'?s|is|correct|right|sahi|hai|ji|haan|ha|sir|madam|guruji|"
    r"ಸರಿ|ಹೌದು|ಸರ್|సరే|అవును|సార్|सही|है|जी|சரி|ஆம்|ശരി|ঠিক|আছে|બરાબર|છે|ਸਹੀ|ਜੀ))*[.!👍🙏 ]*$", re.I)
CONFIRM_NO = re.compile(r"^(no|n|nope|nahi|nahin|na|wrong|incorrect|not correct|galat|change( it)?|not this|illa|ledu|"
                        r"ಇಲ್ಲ|ಬೇಡ|ತಪ್ಪು|కాదు|లేదు|తప్పు|नहीं|नही|गलत|இல்லை|தவறு|അല്ല|ഇല്ല|തെറ്റ്|नाही|चूक|না|ভুল|ના|ખોટું|ਨਹੀਂ|ਗਲਤ)[.! ]*$", re.I)
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

LANGUAGE_Q = ("🗣️ *In which language would you like your horoscope and all my replies?*\n\n"
              "For example: *English, Hindi, Telugu, Kannada, Tamil, Malayalam, Marathi, Bengali, Gujarati, "
              "Punjabi, Odia* or *Hinglish*\n\nJust reply with the language name.")
LANGUAGE_RETRY = "🙏 Please reply with just the language name, for example *Hindi*, *Telugu* or *English*."

# name -> spellings / native-script names customers may type
LANGUAGES = {
    "English": ["english", "eng", "angrezi", "inglish"],
    "Hindi": ["hindi", "hindhi", "हिंदी", "हिन्दी"],
    "Hinglish": ["hinglish"],
    "Telugu": ["telugu", "telgu", "తెలుగు"],
    "Kannada": ["kannada", "kanada", "kannad", "ಕನ್ನಡ"],
    "Tamil": ["tamil", "thamizh", "tamizh", "தமிழ்"],
    "Malayalam": ["malayalam", "malyalam", "മലയാളം"],
    "Marathi": ["marathi", "मराठी"],
    "Bengali": ["bengali", "bangla", "বাংলা"],
    "Gujarati": ["gujarati", "gujrati", "ગુજરાતી"],
    "Punjabi": ["punjabi", "panjabi", "ਪੰਜਾਬੀ"],
    "Odia": ["odia", "oriya", "ଓଡ଼ିଆ"],
    "Assamese": ["assamese", "অসমীয়া"],
    "Urdu": ["urdu", "اردو"],
    "Sanskrit": ["sanskrit", "संस्कृत"],
    "Nepali": ["nepali", "नेपाली"],
    "Konkani": ["konkani", "कोंकणी"],
    "Sindhi": ["sindhi"],
    "Maithili": ["maithili"],
    "Bhojpuri": ["bhojpuri"],
    "Tulu": ["tulu"],
    "Arabic": ["arabic"],
    "French": ["french"],
    "Spanish": ["spanish"],
    "German": ["german"],
}
_LANG_FILLER = re.compile(r"\b(in|language|lang|bhasha|bhasa|bhaasha|please|pls|plz|only|me|mein|main|my|is|i want|want|prefer|choose|reply|replies|ok|okay)\b", re.I)


def parse_language(text: str) -> str:
    """'Hindi', 'in telugu please', 'తెలుగు' -> canonical language name; '' if not recognised."""
    t = (text or "").strip().lower()
    t = re.sub(r"[.!,🙏👍]", " ", t)
    t = _LANG_FILLER.sub(" ", t)
    t = " ".join(t.split())
    if not t:
        return ""
    for name, spellings in LANGUAGES.items():
        if t in spellings:
            return name
    words = t.split()
    found = [name for name, spellings in LANGUAGES.items() if any(w in spellings for w in words)]
    return found[0] if len(found) == 1 else ""


LANGUAGE_CMD = re.compile(r"^\s*(change\s+(my\s+)?)?(language|bhasha|bhasa)(\s+to)?\b\s*(?P<rest>.*)$", re.I)


def place_confirmation(c: dict) -> str:
    place = c.get("resolved_place") or c.get("birth_place", "")
    return i18n.t("place_confirm", c.get("language"), place=place)


PROFILE_FIELDS = ("full_name", "dob", "birth_time", "birth_place")
PLACE_FIELDS = ("birth_place", "resolved_place", "latitude", "longitude", "timezone")
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


def _pick(msg: str) -> str:
    """Language from a menu tap/number ('3', 'Kannada / ಕನ್ನಡ') or a typed name; '' if not recognised."""
    return i18n.menu_choice(msg) or parse_language(msg)


def step(existing: dict | None, phone: str, profile_name: str, text: str, msg_type: str) -> StepResult:
    c = dict(existing or {})
    c["phone_number"] = phone
    if profile_name:
        c["profile_name"] = profile_name
    msg = text.strip()
    is_media = msg_type in ("image", "document")

    if not existing:  # new client: welcome + instructions images, then the language menu
        c["conversation_state"] = "pick_language"
        return StepResult(c, "", action="intro")

    state = c.get("conversation_state") or "onboarding"
    lang = c.get("language", "")

    if RESET_CMD.match(msg):
        for k in PROFILE_FIELDS + CHART_FIELDS + ("consent", "language"):
            c[k] = ""
        c["conversation_state"] = "pick_language"
        return StepResult(c, "", action="intro")

    if state in LEGACY_ONBOARDING:
        state = c["conversation_state"] = "onboarding"

    if state == "pick_language":  # first step of sign-up
        if is_media:  # a Kundali sent before choosing the language: ask for the language first
            return StepResult(c, i18n.PDF_BEFORE_LANGUAGE, action="language_menu")
        chosen = _pick(msg)
        if not chosen:
            return StepResult(c, "", action="language_menu")
        c["language"], c["conversation_state"] = chosen, "onboarding"
        return StepResult(c, i18n.welcome(chosen))

    if state == "onboarding":
        if is_media:
            return StepResult(c, "", action="onboard")
        if not msg or GREETING.match(msg):
            nxt = next_question(c)
            return StepResult(c, i18n.welcome(lang) if nxt == "full_name"
                              else i18n.t("continue", lang) + "\n\n" + i18n.question(nxt, lang))
        return StepResult(c, "", action="onboard")

    if state == "confirm_place":  # all details collected; client checks the place we found on the map
        if CONFIRM_YES.match(msg):
            if not c.get("language"):  # clients who signed up before the language-first menu
                c["conversation_state"] = "choose_language"
                return StepResult(c, "", action="language_menu")
            return StepResult(c, "", action="finish_onboarding")
        if is_media or not msg or GREETING.match(msg):
            return StepResult(c, place_confirmation(c))
        for k in PLACE_FIELDS:
            c[k] = ""
        c["conversation_state"] = "onboarding"
        if CONFIRM_NO.match(msg):
            return StepResult(c, i18n.t("no_problem", lang) + "\n\n" + i18n.question("birth_place", lang))
        return StepResult(c, "", action="onboard")  # the message is the corrected place

    if state == "choose_language":  # (older flow) birthplace confirmed; language chosen -> chart and horoscope
        chosen = _pick(msg)
        if not chosen:
            return StepResult(c, "", action="language_menu")
        c["language"] = chosen
        return StepResult(c, "", action="finish_onboarding")

    if state == "change_language":  # a ready client asked to change the language
        chosen = _pick(msg)
        if not chosen:
            return StepResult(c, "", action="language_menu")
        c["language"], c["conversation_state"] = chosen, "ready"
        return StepResult(c, i18n.t("lang_changed", chosen, name=i18n.native_name(chosen)))

    if state == "confirm_horoscope":  # legacy n8n state
        if YES.match(msg) or HOROSCOPE_CMD.match(msg):
            c["consent"] = "yes"
            c["conversation_state"] = "ready"
            return StepResult(c, i18n.t("generating", lang), action="generate_horoscope")
        c["conversation_state"] = "ready"
        state = "ready"

    if state == "ready":
        if not has_details(c):
            c["conversation_state"] = "onboarding"
            return StepResult(c, i18n.welcome(lang))
        m = LANGUAGE_CMD.match(msg)
        chosen = _pick(m.group("rest")) if m else ""
        if m and (chosen or not m.group("rest").strip(" .!?")):  # "LANGUAGE", "change language", "language hindi"
            if chosen:
                c["language"] = chosen
                return StepResult(c, i18n.t("lang_changed", chosen, name=i18n.native_name(chosen)))
            c["conversation_state"] = "change_language"
            return StepResult(c, "", action="language_menu_image")
        if HOROSCOPE_CMD.match(msg):
            c["consent"] = "yes"
            return StepResult(c, i18n.t("generating", lang), action="generate_horoscope")
        if GREETING.match(msg):
            return StepResult(c, i18n.t("welcome_back", lang, first=c.get("full_name", "").split(" ")[0]))
        return StepResult(c, "", action="answer_question")

    c["conversation_state"] = "pick_language"
    return StepResult(c, "", action="language_menu")


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
