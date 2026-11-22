"""Anthropic Claude (the original provider - same calls as before, only moved here)."""
import base64

import anthropic

from .. import config

NAME = "claude"

# Retries (with backoff) cover rate limits (429), "overloaded" (529), 5xx and network blips under heavy load.
client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=6, timeout=600)

# Server-side refusal fallback is supported on these models; skip it for others.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1", "claude-opus-5"}
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
REFUSAL = "🙏 I'm sorry, I can't help with that request. Please ask me something else about your chart."


def _blocks(content):
    if isinstance(content, str):
        return content
    out = []
    for p in content:
        if p["type"] == "text":
            out.append({"type": "text", "text": p["text"]})
        elif p["type"] == "file":
            b64 = base64.standard_b64encode(p["data"]).decode()
            if p["mime"] == "application/pdf":
                out.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}})
            elif p["mime"] in _IMAGE_TYPES:
                out.append({"type": "image", "source": {"type": "base64", "media_type": p["mime"], "data": b64}})
    return out


def generate(system: str, messages: list[dict], effort: str = "medium") -> str:
    kwargs = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        system=system,
        messages=[{"role": m["role"], "content": _blocks(m["content"])} for m in messages],
        output_config={"effort": effort},
    )
    if config.CLAUDE_MODEL in _FALLBACK_MODELS:
        resp = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
        )
    else:
        resp = client.messages.create(**kwargs)

    if resp.stop_reason == "refusal":
        return REFUSAL
    text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        raise RuntimeError(f"Claude returned no text (stop_reason={resp.stop_reason})")
    return text


def extract(parts: list[dict], schema):
    resp = client.messages.parse(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": _blocks(parts)}],
        output_format=schema,
    )
    if resp.parsed_output is None:
        raise RuntimeError(f"Birth detail extraction failed (stop_reason={resp.stop_reason})")
    return resp.parsed_output
