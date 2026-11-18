"""AstroVinod WhatsApp chatbot - FastAPI entry point.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000
Meta callback URL:  https://<your-public-host>/webhook
"""
import json
import logging

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from app import bot, config, legal, whatsapp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = FastAPI(title="AstroVinod WhatsApp Bot")


@app.on_event("startup")
def _connect_sheets() -> None:
    bot.store()  # fail fast if the database is misconfigured
    logging.getLogger("astrovinod").info("Storage ready: %s", type(bot.store()).__name__)


@app.api_route("/health", methods=["GET", "HEAD"])  # Render health check + uptime pinger (keeps free tier awake)
def health() -> dict:
    return {"ok": True}


@app.get("/privacy", response_class=HTMLResponse)
@app.get("/data-deletion", response_class=HTMLResponse)
def privacy() -> str:
    return legal.PRIVACY_HTML


@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == config.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(q.get("hub.challenge", ""))
    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/webhook")
async def incoming(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not whatsapp.verify_signature(raw, request.headers.get("X-Hub-Signature-256")):
        return Response(status_code=401)
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return Response(status_code=400)
    # Acknowledge Meta immediately; do the slow work (Sheets, Prokerala, Claude) in the background.
    for msg in whatsapp.extract_messages(payload):
        background.add_task(bot.handle, msg)
    return {"ok": True}
