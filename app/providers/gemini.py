"""Google Gemini (settings: GEMINI_API_KEY, GEMINI_MODEL)."""
from google import genai
from google.genai import types

from .. import config

NAME = "gemini"
_SUPPORTED_FILES = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp"}

client = genai.Client(api_key=config.GEMINI_API_KEY)


def _parts(content) -> list:
    if isinstance(content, str):
        return [types.Part.from_text(text=content)]
    out = []
    for p in content:
        if p["type"] == "text":
            out.append(types.Part.from_text(text=p["text"]))
        elif p["type"] == "file" and p["mime"] in _SUPPORTED_FILES:
            out.append(types.Part.from_bytes(data=p["data"], mime_type=p["mime"]))
    return out


def generate(system: str, messages: list[dict], effort: str = "medium") -> str:
    contents = [types.Content(role="model" if m["role"] == "assistant" else "user", parts=_parts(m["content"]))
                for m in messages]
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=16000),
    )
    text = (resp.text or "").strip()
    if not text:
        reason = resp.candidates[0].finish_reason if resp.candidates else "no candidates"
        raise RuntimeError(f"Gemini returned no text ({reason})")
    return text


def extract(parts: list[dict], schema):
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[types.Content(role="user", parts=_parts(parts))],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                           max_output_tokens=16000),
    )
    if isinstance(resp.parsed, schema):
        return resp.parsed
    if resp.text:
        return schema.model_validate_json(resp.text)
    raise RuntimeError("Gemini birth detail extraction returned nothing")
