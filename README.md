# AstroVinod WhatsApp Chatbot

A Python (FastAPI) rewrite of the AstroVinod n8n workflow. The bot uses the WhatsApp Cloud API, Prokerala (kundli data), OpenStreetMap (birthplace lookup) and Claude (readings and answers). **All data is stored in a PostgreSQL database** (a local SQLite file when testing).

## Flow
1. A new user says hi. The bot asks for name → DOB → birth time → birth place, then asks for consent (YES/NO).
2. YES: the bot geocodes the birthplace, resolves its real timezone, fetches the Prokerala advanced kundli, has Claude write the horoscope, and sends it on WhatsApp.
3. In the `ready` state, any message, image or PDF is answered by Claude. Claude gets the client's chart, the last 20 messages and the attached file.
4. Commands: `HOROSCOPE` regenerates the report. `RESET` re-collects the birth details.

## Daily / weekly / monthly guidance ([app/intents.py](app/intents.py))
The bot detects natural variations of the trigger questions in English and Hinglish. Examples: "How will my day be?", "plan my week", "is mahine kaisa rahega", "next month?".
Each request gets real data: the client's natal chart, the running Mahadasha/Antardasha/Pratyantardasha, planet sign changes and retrogrades in the period, the Moon's position each day (Chandrashtama days are flagged), and for daily guidance the panchang (tithi, Rahu Kaal, Abhijit Muhurat, horas). Each period has a fixed answer format, set in `GUIDANCE_FORMATS` in [app/ai.py](app/ai.py).

## Chart engine ([app/vedic.py](app/vedic.py))
Charts are computed locally from NASA JPL DE421 data (via Skyfield), with Lahiri ayanamsa, whole-sign houses and Vimshottari dasha. This costs nothing and needs no API credits. On first run the bot downloads the ~17 MB ephemeris file into `data/`.
Prokerala is optional. Its extra data (yogas, doshas) is added when the account has credits and skipped otherwise.

## Database ([app/db.py](app/db.py))
- `DATABASE_URL` set → PostgreSQL. Use [Neon](https://neon.tech): its free plan never expires, unlike Render's free Postgres, which is deleted after 30 days.
- `DATABASE_URL` empty → `data/astrovinod.db` (SQLite, local testing only, because Render's free disk is wiped on restart).
- Tables are created automatically:
  - **customers**: phone_number, profile_name, full_name, dob, birth_time, birth_place, resolved_place, latitude, longitude, timezone, consent, conversation_state, chart_summary, kundli_pdf_notes, last_message_id, created_at, updated_at
  - **chat_history**: id, timestamp, phone_number, message_id, role, message_type, message
- View the data in Neon's **Tables** page, or run SQL in its **SQL Editor**.
- Google Sheet storage is still available as an option (`STORAGE=google_sheet`, see [google_sheet_script/Code.gs](google_sheet_script/Code.gs)).

## Setup
1. **Google service account** (n8n's OAuth login can't be exported):
   - Google Cloud Console → enable the **Google Sheets API** → IAM → Service Accounts → create one → Keys → Add key → JSON.
   - Save the key as `service_account.json` in this folder.
   - Open the sheet and **Share** it with the service account's `client_email` as **Editor**.
2. Check `.env` (the credentials were extracted from the workflow). Optional: set `META_APP_SECRET` to turn on webhook signature checks.
3. Install and run:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   .\.venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. Give the server a public HTTPS URL. For testing use `ngrok http 8000`. For production use Render, Railway or a VPS.
5. Meta Developer Console → WhatsApp → Configuration → Callback URL `https://<host>/webhook`, Verify token = `WHATSAPP_VERIFY_TOKEN`. Subscribe to **messages**.
   Turn off the n8n workflow first, or both will reply.

## Deploy on Render (free tier)
1. Push this folder to a **private** GitHub repo. `.env` and `service_account.json` are git-ignored and must never be pushed.
2. Render → **New → Blueprint** → pick the repo. Render reads [render.yaml](render.yaml).
3. Fill in the secret variables it asks for, copying them from `.env`. For `GOOGLE_SERVICE_ACCOUNT_JSON`, paste the **entire contents** of the service-account JSON file.
4. After the deploy, your callback URL is `https://<service-name>.onrender.com/webhook`. Check that `https://<service-name>.onrender.com/health` shows `{"ok":true}`.
5. Free instances sleep after 15 minutes without traffic, so the first message after a quiet period waits about 1 minute. To prevent this, add a free [UptimeRobot](https://uptimerobot.com) HTTP monitor on `/health` every 5 minutes. One always-on service fits within Render's free 750 hours/month.

## Fixes over the n8n version
- Replies are sent in WhatsApp format instead of markdown, and long replies are split at paragraph breaks.
- Duplicate webhook retries from Meta are ignored, so users no longer get double replies.
- Birth time uses the birthplace's real historical timezone instead of a hard-coded +05:30.
- Images and PDFs are downloaded and sent to Claude so it can actually analyse them.
- Every bot reply is now logged. Before, conversational replies were never logged, and the horoscope log row read a phone number that didn't exist.
- Follow-up questions are answered from the stored chart and as a real multi-turn conversation.
- Uses the current model `claude-opus-5-5` (the old `claude-3-5-sonnet-20241022` is retired). Set `CLAUDE_MODEL=claude-sonnet-5-5` to cut costs.
- Secrets are kept in `.env` instead of inside node settings. Sheet writes use RAW input so phone numbers stay intact and formulas can't be injected.
