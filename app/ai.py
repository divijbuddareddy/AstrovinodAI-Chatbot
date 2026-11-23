"""AI prompts for horoscope reports and conversational answers.

The prompts live here and are the same for every AI. Which AI answers (Claude, Gemini or OpenAI) is chosen with the
AI_PROVIDER setting - see app/providers/.
"""
import json
from datetime import date

from pydantic import BaseModel, Field

from . import providers
from .astrologer_style import ASTROLOGER_STYLE

_FILE_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp"}

STYLE = """How you write (the reply is sent on WhatsApp):
- WhatsApp formatting only: *bold*, _italic_, simple "•" bullet lines. No markdown headings (#), tables or code blocks.
- Chat replies are short and conversational, like a real astrologer texting a client: usually 3-8 lines.
  Only write long, structured answers for the full horoscope, daily/weekly/monthly guidance, or when the client asks for a detailed analysis.
- Reply in the client's language and script (English, Hindi, Hinglish, Kannada, etc.), matching how they write to you."""

BASE_SYSTEM = f"""You are AstroVinod AI, "Your Personal Astrologer": the client's own personal Vedic astrologer, a warm and experienced Guruji they consult
over WhatsApp. You are not a generic AI assistant; this is a one-to-one relationship with a client whose chart you know.

How you behave:
- Address the client by their first name, warmly and respectfully. Begin naturally (for example "🙏 Namaste Ravi ji"), but don't repeat the same greeting every message.
- Always speak from *their* chart: name the specific placements behind what you say (e.g. "your Moon in Rohini",
  "Saturn in your 10th house", "your running Venus Mahadasha"). Never give generic sun-sign style answers.
- Remember the conversation: refer back to what they told you earlier (their worries, job, relationship, earlier questions)
  and follow up on it, the way a family astrologer would.
- For timing questions (today, this week, this month, this year, "when will I get married/a job"), combine their dasha
  periods with current planetary transits relative to their Moon sign and Lagna, and give clear, time-bound guidance.
- Be caring and encouraging, but honest. Frame difficult periods with practical advice and simple remedies:
  mantras, a day of the week to fast or donate, colours, charity, temple visits, behavioural advice. Suggest gemstones
  only with care, and add that they should be worn after consultation.
- When it helps, end with a gentle follow-up question to understand their situation better (e.g. "Are you currently
  in a job or looking for a change?").
- If they send a chart image or PDF, read it carefully and explain what it shows for them personally.
- Speak to the client as "you" (the client's documents call them "the native").
- If something is outside astrology, gently bring the conversation back to their chart and life guidance.

Boundaries (stay in character while keeping them):
- Astrology is guidance, not certainty. Never predict death, serious illness or accidents, and never tell anyone to stop
  medical treatment, take financial or legal risks, or end a relationship purely because of the chart.
- For health, money or legal worries, give astrological perspective and remedies and also advise them to consult a doctor or professional.
- Never invent chart facts. If the kundli data doesn't contain something, reason from the birth details you do have.

{ASTROLOGER_STYLE}

{STYLE}"""


def _profile_block(c: dict) -> str:
    lines = [
        f"Name: {c.get('full_name', '')}",
        f"Date of birth: {c.get('dob', '')}",
        f"Time of birth: {c.get('birth_time', '')} (24h, local time)",
        f"Place of birth: {c.get('resolved_place') or c.get('birth_place', '')}",
    ]
    if c.get("timezone"):
        lines.append(f"Timezone: {c['timezone']}")
    if c.get("kundli_pdf_notes"):
        lines.append("\nCLIENT'S OWN KUNDALI (from the PDF they uploaded - treat it as their reference chart; "
                     "use the computed data below for current transits and dates):\n" + c["kundli_pdf_notes"])
    return "\n".join(lines)


def _call(system: str, messages: list[dict], effort: str = "medium") -> str:
    return providers.get().generate(system, messages, effort)


def _file_part(media: bytes | None, media_mime: str) -> list[dict]:
    return [{"type": "file", "mime": media_mime, "data": media}] if media and media_mime in _FILE_TYPES else []


# ---- Client-supplied guidance formats (3. Daily / 4. Weekly / 5. Monthly Guidance Prompt.docx) ----
_COMMON_SECTIONS = """*😌 Dominant Emotions:* {emotions}
*💰 Finances:* {finances}
*💼 Office & Work Life:* {work}
*🧘 Health:* {health}
*❤️ Love Life:* {love}
*🤝 Relationships:* {relationships}"""

GUIDANCE_FORMATS = {
    "DAILY_GUIDANCE": {
        "title": "🌅 *Daily Astrological Guidance – {label}*",
        "sections": _COMMON_SECTIONS.format(
            emotions="emotional state, mood, mental clarity and inner feelings",
            finances="financial opportunities, expenses, gains and monetary decisions",
            work="work pressure, office politics, appreciation, recognition, conflicts and professional opportunities",
            health="physical energy, mental well-being and possible health concerns",
            love="romance, emotional bonding, intimacy and partner interactions",
            relationships="family, friends, colleagues, communication and social interactions",
        ) + """
*🧭 Strategy for the Day:* practical actions, opportunities to utilise, situations to avoid and the best approach to navigate the day (mention the favourable time window and Rahu Kaal from the panchang)
*🔑 Key Advice for the Day:* one short line""",
        "instructions": """- Consider current planetary transits in relation to the natal chart and running Dashas.
- Provide specific, practical and balanced predictions.
- Avoid generic statements and unnecessary repetition.
- Clearly distinguish favourable and challenging influences.""",
    },
    "WEEKLY_GUIDANCE": {
        "title": "📅 *Weekly Astrological Guidance – {label}*",
        "sections": _COMMON_SECTIONS.format(
            emotions="emotional patterns, mental state, mood and inner feelings throughout the week",
            finances="income, expenses, financial opportunities, gains, losses and important monetary decisions",
            work="work pressure, office politics, appreciation, recognition, conflicts, workload and career opportunities",
            health="physical energy, mental well-being, health vulnerabilities and areas requiring attention",
            love="romantic developments, emotional bonding, intimacy and partner interactions",
            relationships="family dynamics, friendships, social interactions and interpersonal challenges",
        ) + """
*🧭 Strategy for the Week:* important actions to take, opportunities to utilise, challenges to manage and situations to avoid
*📆 Important Days:* the days (date + weekday) when favourable or challenging influences are stronger, wherever identifiable
*🔭 Weekly Outlook:* a short summary of the overall theme of the week
*🔑 Key Advice for the Week:* one line""",
        "instructions": """- Consider weekly planetary transits in relation to the natal chart and running Dashas.
- Identify significant planetary movements and their influence during the week.
- Highlight important days when favourable or challenging influences are stronger, wherever identifiable (use the daily Moon data; Chandrashtama days are challenging).
- Provide practical, personalised and balanced predictions.
- Avoid generic statements and unnecessary repetition.
- Distinguish between favourable opportunities and potential challenges.""",
    },
    "MONTHLY_GUIDANCE": {
        "title": "🗓️ *Monthly Astrological Guidance – {label}*",
        "sections": _COMMON_SECTIONS.format(
            emotions="emotional patterns, mental state, mood, confidence and psychological well-being throughout the month",
            finances="income, expenses, investments, financial opportunities, gains, losses and important monetary decisions",
            work="career progress, workload, office politics, recognition, appreciation, conflicts, professional opportunities and workplace challenges",
            health="physical vitality, mental health, possible health vulnerabilities and areas requiring attention",
            love="romantic developments, emotional bonding, intimacy and relationship stability",
            relationships="family dynamics, friendships, social connections, communication and interpersonal challenges",
        ) + """
*🚀 Career & Business:* professional growth, business opportunities, partnerships, new ventures and decision-making
*📌 Important Periods:* favourable and challenging dates or periods during the month based on significant transits and Dasha influences
*🧭 Strategy for the Month:* important actions to take, opportunities to utilise, risks to manage and situations to avoid
*🔭 Monthly Outlook:* about 50 words summarising the overall theme and major developments expected during the month
*🔑 Key Advice for the Month:* one clear and actionable recommendation""",
        "instructions": """- Analyse monthly planetary transits in relation to the natal chart and running Mahadasha/Antardasha.
- Give importance to house activation, planetary aspects, conjunctions and significant transit changes.
- Identify how planetary influences may manifest in practical life experiences.
- Distinguish between favourable, mixed and challenging periods.
- Provide specific, realistic and balanced predictions.
- Avoid generic statements, repetition and unnecessary astrological jargon.
- Do not make definitive predictions where the astrological indications are inconclusive.""",
    },
}


def _language_rule(customer: dict) -> str:
    lang = (customer.get("language") or "").strip()
    if not lang:
        return ""
    if lang.lower() == "hinglish":
        how = "Hinglish (Hindi written in English/Roman letters, mixed with English words)"
    elif lang.lower() == "english":
        how = "English"
    else:
        how = f"{lang}, written in the {lang} script"
    return (f"\n\nLANGUAGE (the client chose this - it overrides any other language instruction): write your ENTIRE reply "
            f"ONLY in {how}, even if the client writes to you in English or another language, and even if earlier "
            f"messages in this chat were in another language. Section titles and bullet points too. Astrology terms "
            f"(Lagna, Nakshatra, Mahadasha, house names) may stay as they are, but explain them in {lang}.")


def _system(customer: dict, chart: dict, now_ctx: dict) -> str:
    return f"""{BASE_SYSTEM}{_language_rule(customer)}

Today's date: {date.today().isoformat()}

CLIENT PROFILE
{_profile_block(customer)}

CLIENT'S NATAL KUNDLI (computed: sidereal / Lahiri, whole-sign houses, Vimshottari dasha)
{json.dumps(chart, ensure_ascii=False, separators=(",", ":"))}

RIGHT NOW (running dasha and today's planetary transits relative to their Lagna and Moon)
{json.dumps(now_ctx, ensure_ascii=False, separators=(",", ":"))}

Use the data above as the source of truth for placements, dashas and transits. Never ask for birth details again."""


def _with_history(history: list[dict], content: list[dict]) -> list[dict]:
    messages = _history_to_messages(history)
    if messages and messages[-1]["role"] == "user":
        # keep strict alternation: fold the trailing user turn into this one
        prev = messages.pop()["content"]
        content.insert(len(content) - 1, {"type": "text", "text": prev})
    messages.append({"role": "user", "content": content})
    return messages


def horoscope_report(customer: dict, chart: dict, now_ctx: dict) -> str:
    # Client-supplied master prompt (2. Chart analysis master prompt.docx)
    user = """BIRTH CHART ANALYSIS BASED ON VEDIC ASTROLOGY FOR PERSONAL GUIDANCE AND DECISION MAKING

Write this as a personal message to the client: address them by first name and speak to them as "you".
Use the birth chart data above, including "birth_panchanga" (Tithi, Vara, Nakshatra, Yoga, Karana at birth).
Format for WhatsApp: bold section titles, numbered points, short paragraphs. Start with one warm line of greeting.

*Section A – Panchanga Analysis*
Perform a detailed Panchanga analysis using the given birth data.
- Analyse the Five Panchanga Parameters: explain Tithi, Vara, Nakshatra, Yoga and Karana individually, focusing on their
  influence on the native's personality, life experiences, strengths, challenges and destiny. About 50 words for each parameter.
- Integrated Panchanga Analysis: interpret how all five parameters interact and complement each other. Identify the
  dominant themes and recurring patterns in the native's life.
- Destiny Line: based on the combined influence of all five parameters, write a meaningful destiny statement capturing
  the native's overall life direction, purpose, opportunities and challenges. About 50 words.

*Section B – 10 Key Characteristics*
Based on the birth chart and Panchanga details, identify the 10 key characteristics of the native: personality, mindset,
behaviour, strengths, weaknesses, relationships, career approach, decision-making and overall nature.
Present them as 10 clear, numbered points. Keep each concise, specific and insightful. For each, add a brief
evidence-based rationale naming the chart inputs it comes from (e.g. "Moon in Chitra, 1st house").
Consider the combined planetary and Panchanga influences.

*Section C – Strengths and Weaknesses*
Based on the birth chart and Panchanga details, identify the native's 5 major strengths and 5 major weaknesses,
considering planetary influences, house placements and Panchanga parameters.
Present them under two headings:
- Five Major Strengths: key advantages, talents and favourable qualities.
- Five Major Weaknesses: challenges, limitations and areas requiring improvement.
Keep each point concise, practical and specific to the native.

Instructions for all sections:
- Use authentic Vedic astrology principles.
- Keep the analysis clear, structured and specific to the native. Avoid generic statements and unnecessary repetition.
- Explain the astrological significance in terms of practical life experiences.
- Maintain a balanced, objective perspective covering both positive and challenging influences.

End with one line inviting them to ask any question, or to ask for their daily, weekly or monthly guidance."""
    return _call(_system(customer, chart, now_ctx), [{"role": "user", "content": user}], effort="high")


def periodic_guidance(customer: dict, chart: dict, now_ctx: dict, intent, period_data: dict,
                      history: list[dict], question: str) -> str:
    f = GUIDANCE_FORMATS[intent.id]
    instruction = f"""[{intent.id}] The client asked: "{question}"

Based on the native's birth chart, the planetary transits for this period and the running Mahadasha/Antardasha,
provide personalised guidance for {intent.label} ({intent.start.isoformat()} to {intent.end.isoformat()}).
Give approximately 25 words for each aspect. If the question focuses on one area (e.g. finances), keep the
structure but add a little more depth there. Start with a one-line personal greeting using their first name.

Use exactly this structure (WhatsApp formatting):

{f["title"].format(label=intent.label)}

{f["sections"]}

Instructions:
{f["instructions"]}

PERIOD DATA (transits, planet events, daily Moon, panchang)
{json.dumps(period_data, ensure_ascii=False, separators=(",", ":"))}"""
    messages = _with_history(history, [{"type": "text", "text": instruction}])
    return _call(_system(customer, chart, now_ctx), messages, effort="medium")


def answer_question(customer: dict, chart: dict, now_ctx: dict, history: list[dict], question: str,
                    media: bytes | None = None, media_mime: str = "") -> str:
    content = _file_part(media, media_mime) + [{"type": "text", "text": question}]
    return _call(_system(customer, chart, now_ctx), _with_history(history, content), effort="medium")


def _history_to_messages(history: list[dict]) -> list[dict]:
    """Convert sheet rows to an alternating user/assistant message list."""
    msgs: list[dict] = []
    for row in history:
        role = "assistant" if row.get("role") == "assistant" else "user"
        text = str(row.get("message", "")).strip()
        if not text:
            continue
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n\n" + text
        else:
            msgs.append({"role": role, "content": text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    return msgs


class BirthDetails(BaseModel):
    full_name: str = Field(description="Client's full name, or empty string if not given")
    date_of_birth: str = Field(description="YYYY-MM-DD, or empty string if not given")
    time_of_birth: str = Field(description="HH:MM in 24-hour format, or empty string if not given")
    time_is_ambiguous: bool = Field(description="True if a time was given without AM/PM and it could be either")
    place_of_birth: str = Field(description="City, State, Country, or empty string if not given")
    is_birth_chart: bool = Field(description="True if the attached file is a birth chart / kundali")
    chart_notes: str = Field(description="If the file is a kundali: compact summary of its natal data (Lagna, planets with sign/house/nakshatra, Moon sign, nakshatra, dasha table). Otherwise empty string")


def extract_birth_details(known: dict, text: str = "", media: bytes | None = None, media_mime: str = "",
                          last_bot_message: str = "") -> BirthDetails:
    """Read birth details from a free-text message or an uploaded kundali PDF/image (welcome flow)."""
    content = _file_part(media, media_mime)
    known_json = json.dumps({k: known.get(k, "") for k in ("full_name", "dob", "birth_time", "birth_place")})
    content.append({"type": "text", "text": f"""Extract birth details for an astrology client.

Already known: {known_json}
Our previous message to the client: {last_bot_message[-600:]!r}
Client's reply: {text!r}

Rules:
- Extract only what is stated in the message or the attached file; never guess. Return "" for anything missing.
- Dates are day-first (Indian format): 05/06/1990 is 5 June 1990. Accept written months too.
- Convert times to 24-hour HH:MM. If no AM/PM is given and the hour is 1-12, set time_is_ambiguous (unless context such as "evening" makes it clear).
- Place: "City, State, Country". You may add the state/country when the city is well known and unambiguous."""})
    return providers.get().extract(content, BirthDetails)
