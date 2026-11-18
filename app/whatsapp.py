"""WhatsApp Cloud API helpers: parse webhooks, send text, download media."""
import hashlib
import hmac

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

                if mtype == "text":
                    text = msg.get("text", {}).get("body", "")
                elif mtype == "button":
                    text = msg.get("button", {}).get("text", "")
                elif mtype == "interactive":
                    inter = msg.get("interactive", {})
                    text = (inter.get("button_reply") or {}).get("title") or (inter.get("list_reply") or {}).get("title") or ""
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


def send_text(to: str, body: str) -> str:
    """Send one text message, return the WhatsApp message id."""
    resp = requests.post(
        f"{GRAPH}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages",
        headers={**_HEADERS, "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"WhatsApp send failed ({resp.status_code}): {resp.text}")
    return (resp.json().get("messages") or [{}])[0].get("id", "")


def download_media(media_id: str) -> tuple[bytes, str]:
    meta = requests.get(f"{GRAPH}/{media_id}", headers=_HEADERS, timeout=30)
    meta.raise_for_status()
    info = meta.json()
    data = requests.get(info["url"], headers=_HEADERS, timeout=60)
    data.raise_for_status()
    return data.content, info.get("mime_type", "")
