"""Flexible detection of DAILY / WEEKLY / MONTHLY guidance requests.

Matches natural variations ("How will my day be?", "plan my week", "is mahine kaisa rahega",
"Guide me for the coming month, Guruji") instead of exact phrases.
A message needs (a) a time-period word and (b) a guidance/prediction cue.
"""
import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

_I = re.I

DAY = re.compile(r"\b(today|today'?s|todays|tonight|daily|this day|my day|the day|aaj|aj ka|aaj ka|aaj ki|din|dinbhavishya|tomorrow|tomorrow'?s)\b", _I)
WEEK = re.compile(r"\b(week|weeks|week'?s|weekly|weekend|hafta|hafte|haftey|saptah|saptahik)\b", _I)
MONTH = re.compile(r"\b(month|months|month'?s|monthly|mahina|mahine|maheena|mahinay|maas|masik)\b", _I)
NEXT = re.compile(r"\b(next|coming up next|agle|agla|agli|tomorrow|tomorrow'?s)\b", _I)

CUE = re.compile(
    r"(predict|prediction|horoscope|rashifal|bhavishya|forecast|guidance|guide|astrolog|"
    r"expect|in store|plan\b|planning|how will|how would|how is|how's|how does|how do|what will|what is in|"
    r"lucky|auspicious|shubh|muhurat|opportunit|challeng|careful|caution|avoid|developments|"
    r"financ|money|career|job|business|love|relationship|health|"
    r"kaisa|kaisi|kaise|rahega|rahegi|batao|bataiye|tell me|what about|how about|guruji)",
    _I,
)


@dataclass
class Intent:
    id: str          # DAILY_GUIDANCE | WEEKLY_GUIDANCE | MONTHLY_GUIDANCE
    start: date
    end: date
    label: str


def detect(text: str, today: date) -> Intent | None:
    msg = text.strip()
    if not msg or not CUE.search(msg):
        return None
    nxt = bool(NEXT.search(msg))

    if MONTH.search(msg):
        y, m = today.year, today.month
        if nxt and not re.search(r"\b(this|current|is)\s+(month|mahin)", msg, _I):
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])
        return Intent("MONTHLY_GUIDANCE", start, end, start.strftime("%B %Y"))

    if WEEK.search(msg):
        if nxt and not re.search(r"\b(this|current|is)\s+(week|hafte)", msg, _I):
            start = today + timedelta(days=7 - today.weekday())  # next Monday
        else:
            start = today  # "this week" = the upcoming 7 days
        end = start + timedelta(days=6)
        return Intent("WEEKLY_GUIDANCE", start, end, f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}")

    if DAY.search(msg) or re.search(r"\blucky time\b", msg, _I):
        d = today + timedelta(days=1) if re.search(r"\btomorrow", msg, _I) else today
        return Intent("DAILY_GUIDANCE", d, d, d.strftime("%A, %d %B %Y"))

    return None
