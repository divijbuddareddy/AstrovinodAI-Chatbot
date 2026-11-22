"""Which AI writes the replies. Chosen with the AI_PROVIDER setting: claude (default) | gemini | openai.

Every provider module offers the same two functions:
  generate(system, messages, effort) -> str          reply text
  extract(parts, schema) -> schema instance           structured data (birth details)

Messages are [{"role": "user" | "assistant", "content": str | list[part]}] and parts are
  {"type": "text", "text": "..."}  or  {"type": "file", "mime": "application/pdf" | "image/png" ..., "data": bytes}

If the chosen provider is missing its key or model, Claude is used instead (with a warning), so the bot keeps working.
"""
import logging

from .. import config

log = logging.getLogger("astrovinod")
_provider = None


def get():
    global _provider
    if _provider is None:
        name = config.AI_PROVIDER
        if name == "gemini" and config.GEMINI_API_KEY and config.GEMINI_MODEL:
            from . import gemini as _provider
        elif name == "openai" and config.OPENAI_API_KEY and config.OPENAI_MODEL:
            from . import openai as _provider
        else:
            if name not in ("claude", ""):
                log.warning("AI_PROVIDER=%s but its API key or model is not set - using Claude instead", name)
            from . import claude as _provider
        log.info("AI provider: %s", _provider.NAME)
    return _provider
