"""WhatsApp Cloud API helpers: parse webhooks, send text, download media."""
import hashlib
import hmac
import random
import time

import requests

from . import config

GRAPH = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}"
_HEADERS = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"}
MAX_WA_CHARS = 3500  # WhatsApp hard limit is 4096


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256. Skipped when META_APP_SECRET is not configured."""
    if not config.META_APP_SECRET:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(config.META_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[7:])


def extract_messages(payload: dict) -> list[dict]:
    """Turn a Meta webhook payload into a list of normalized inbound messages."""
    out = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            contacts = value.get("contacts", []) or []
            for msg in value.get("messages", []) or []:  # status callbacks have no "messages"
                phone = "".join(ch for ch in str(msg.get("from", "")) if ch.isdigit())
                if not phone:
                    continue
                contact = next((c for c in contacts if c.get("wa_id") == msg.get("from")), contacts[0] if contacts else {})
                mtype = msg.get("type", "")
                text, media_id, mime, filename = "", "", "", ""
                emoji, reacted_to, reply_id = "", "", ""

                if mtype == "reaction":  # client long-pressed one of our messages and tapped an emoji
                    react = msg.get("reaction", {}) or {}
                    emoji, reacted_to = react.get("emoji", "") or "", react.get("message_id", "") or ""
                elif mtype == "text":
                    text = msg.get("text", {}).get("body", "")
                elif mtype == "button":
                    text = msg.get("button", {}).get("text", "")
                elif mtype == "interactive":
                    inter = msg.get("interactive", {})
                    chosen = inter.get("button_reply") or inter.get("list_reply") or {}
                    text, reply_id = chosen.get("title") or "", chosen.get("id") or ""
                elif mtype == "image":
                    img = msg.get("image", {})
                    media_id, mime = img.get("id", ""), img.get("mime_type", "image/jpeg")
                    text = img.get("caption") or "Please analyse this image."
                elif mtype == "document":
                    doc = msg.get("document", {})
                    media_id, mime = doc.get("id", ""), doc.get("mime_type", "")
                    filename = doc.get("filename", "document")
                    text = doc.get("caption") or f"Please analyse this document ({filename})."
                else:
                    text = ""  # audio, video, sticker, location... handled as unsupported

                out.append({
                    "phone": phone,
                    "profile_name": (contact.get("profile") or {}).get("name", ""),
                    "message_id": msg.get("id", ""),
                    "timestamp": msg.get("timestamp", ""),
                    "type": mtype,
                    "text": (text or "").strip(),
                    "media_id": media_id,
                    "mime_type": mime,
                    "filename": filename,
                    "emoji": emoji,            # reactions only ("" when a reaction is removed)
                    "reacted_to": reacted_to,  # reactions only: id of our message they reacted to
                    "reply_id": reply_id,
                    "context_id": (msg.get("context") or {}).get("id", ""),
                })
    return out


def split_message(text: str, limit: int = MAX_WA_CHARS) -> list[str]:
    chunks, remaining = [], text.strip()
    while len(remaining) > limit:
        cut = remaining.rfind("\n\n", 0, limit)
        if cut < limit * 0.5:
            cut = remaining.rfind("\n", 0, limit)
        if cut < limit * 0.5:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _with_retries(do, attempts: int = 5):
    """Call do() -> Response; retry rate limits (429), Meta 5xx and network errors with backoff."""
    for i in range(attempts):
        try:
            resp = do()
        except requests.RequestException:
            if i == attempts - 1:
                raise
        else:
            if resp.status_code != 429 and resp.status_code < 500:
                return resp
            if i == attempts - 1:
                return resp
        time.sleep(min(2 ** i, 20) + random.random())


def _post_message(payload: dict, label: str) -> str:
    resp = _with_retries(lambda: requests.post(
        f"{GRAPH}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages",
        headers={**_HEADERS, "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "recipient_type": "individual", **payload},
        timeout=30,
    ))
    if resp.status_code >= 400:
        raise RuntimeError(f"WhatsApp {label} failed ({resp.status_code}): {resp.text}")
    return (resp.json().get("messages") or [{}])[0].get("id", "")


def send_text(to: str, body: str) -> str:
    """Send one text message, return the WhatsApp message id."""
    return _post_message({"to": to, "type": "text", "text": {"preview_url": False, "body": body}}, "send")


def send_image(to: str, link: str, caption: str = "") -> str:
    """Send an image by public HTTPS link (JPG/PNG, max 5 MB); returns the WhatsApp message id."""
    image = {"link": link}
    if caption:
        image["caption"] = caption[:1024]
    return _post_message({"to": to, "type": "image", "image": image}, "image send")


def send_list(to: str, body: str, button: str, rows: list[tuple[str, str]], section: str = "Languages") -> str:
    """Send a tap-to-choose list (WhatsApp interactive list, max 10 rows). rows = [(id, title<=24 chars)].
    The client's tap comes back as an 'interactive' message whose text is the row title."""
    return _post_message({
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body[:1024]},
            "action": {"button": button[:20], "sections": [{
                "title": section[:24],
                "rows": [{"id": rid[:200], "title": title[:24]} for rid, title in rows[:10]],
            }]},
        },
    }, "list send")


def send_buttons(to: str, body: str, buttons: list[tuple[str, str]], image_link: str = "") -> str:
    """Send up to 3 tap-to-reply buttons, optionally with an image header. buttons = [(id, title<=20 chars)]."""
    interactive: dict = {
        "type": "button",
        "body": {"text": body[:1024]},
        "action": {"buttons": [
            {"type": "reply", "reply": {"id": bid[:256], "title": title[:20]}} for bid, title in buttons[:3]
        ]},
    }
    if image_link:
        interactive["header"] = {"type": "image", "image": {"link": image_link}}
    return _post_message({"to": to, "type": "interactive", "interactive": interactive}, "buttons send")


def send_cta_url(to: str, body: str, button_text: str, url: str, footer: str = "") -> str:
    """Send an interactive CTA URL button so tapping opens the URL directly."""
    interactive: dict = {
        "type": "cta_url",
        "body": {"text": body[:1024]},
        "action": {"name": "cta_url", "parameters": {"display_text": button_text[:20], "url": url}},
    }
    if footer:
        interactive["footer"] = {"text": footer[:60]}
    return _post_message({"to": to, "type": "interactive", "interactive": interactive}, "cta_url send")


def download_media(media_id: str) -> tuple[bytes, str]:
    meta = _with_retries(lambda: requests.get(f"{GRAPH}/{media_id}", headers=_HEADERS, timeout=30))
    meta.raise_for_status()
    info = meta.json()
    data = _with_retries(lambda: requests.get(info["url"], headers=_HEADERS, timeout=60))
    data.raise_for_status()
    return data.content, info.get("mime_type", "")
