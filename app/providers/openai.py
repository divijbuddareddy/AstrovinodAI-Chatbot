"""OpenAI / ChatGPT models (settings: OPENAI_API_KEY, OPENAI_MODEL). Uses the Responses API."""
import base64

from openai import OpenAI

from .. import config

NAME = "openai"
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

client = OpenAI(api_key=config.OPENAI_API_KEY, max_retries=6, timeout=600)


def _content(content):
    if isinstance(content, str):
        return content
    out = []
    for p in content:
        if p["type"] == "text":
            out.append({"type": "input_text", "text": p["text"]})
        elif p["type"] == "file":
            b64 = base64.standard_b64encode(p["data"]).decode()
            if p["mime"] == "application/pdf":
                out.append({"type": "input_file", "filename": "kundli.pdf",
                            "file_data": f"data:application/pdf;base64,{b64}"})
            elif p["mime"] in _IMAGE_TYPES:
                out.append({"type": "input_image", "image_url": f"data:{p['mime']};base64,{b64}"})
    return out


def generate(system: str, messages: list[dict], effort: str = "medium") -> str:
    resp = client.responses.create(
        model=config.OPENAI_MODEL,
        instructions=system,
        input=[{"role": m["role"], "content": _content(m["content"])} for m in messages],
        max_output_tokens=16000,
    )
    text = (resp.output_text or "").strip()
    if not text:
        raise RuntimeError(f"OpenAI returned no text (status={resp.status})")
    return text


def extract(parts: list[dict], schema):
    resp = client.responses.parse(
        model=config.OPENAI_MODEL,
        input=[{"role": "user", "content": _content(parts)}],
        text_format=schema,
        max_output_tokens=16000,
    )
    if resp.output_parsed is None:
        raise RuntimeError(f"OpenAI birth detail extraction failed (status={resp.status})")
    return resp.output_parsed
