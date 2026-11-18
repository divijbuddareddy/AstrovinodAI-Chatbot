"""Public Privacy Policy / Data Deletion page (required by Meta to publish the WhatsApp app)."""

CONTACT_EMAIL = "astrovinod.karma@gmail.com"
LAST_UPDATED = "18 November 2026"

PRIVACY_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AstroVinod AI – Privacy Policy</title>
<style>
  :root {{ --bg:#fbf8f3; --text:#2b2233; --muted:#6b6175; --accent:#5b3a8c; --line:#e6dfd3; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#17131c; --text:#ece6f2; --muted:#a99fb5; --accent:#c4a8f0; --line:#2f2838; }} }}
  body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.65 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
  main {{ max-width:760px; margin:0 auto; padding:40px 16px 64px; }}
  h1 {{ font-size:1.9rem; margin:0 0 4px; color:var(--accent); }}
  h2 {{ font-size:1.15rem; margin:32px 0 8px; padding-top:16px; border-top:1px solid var(--line); }}
  p, li {{ color:var(--text); }} .muted {{ color:var(--muted); font-size:.9rem; }}
  a {{ color:var(--accent); }} ul {{ padding-left:1.2rem; }}
</style>
</head>
<body><main>
<h1>AstroVinod AI – Privacy Policy</h1>
<p class="muted">Last updated: {LAST_UPDATED}</p>

<p>AstroVinod AI ("we", "us") is a Vedic astrology assistant available on WhatsApp. This policy explains what
information we collect when you chat with us, how we use it, and the choices you have.</p>

<h2>Information we collect</h2>
<ul>
  <li><b>WhatsApp details:</b> your WhatsApp phone number and profile name.</li>
  <li><b>Birth details you share:</b> full name, date of birth, time of birth and place of birth.</li>
  <li><b>Messages and files:</b> the messages you send us and any birth chart (Kundali) PDFs or images you upload.</li>
  <li><b>Generated content:</b> your calculated birth chart and the readings and guidance we send you.</li>
</ul>

<h2>How we use your information</h2>
<ul>
  <li>To calculate your Vedic birth chart and provide personalised astrological readings and guidance.</li>
  <li>To remember your profile and conversation so you don't have to repeat your details.</li>
  <li>To operate, secure and improve the service.</li>
</ul>
<p>We do not sell your personal information and we do not use it for advertising.</p>

<h2>Service providers</h2>
<p>We share information only with providers that help us run the service, and only as needed:</p>
<ul>
  <li><b>Meta (WhatsApp Business Platform)</b> – delivers messages between you and us.</li>
  <li><b>Anthropic (Claude AI)</b> – generates the written readings from your chart data and messages.</li>
  <li><b>Neon (PostgreSQL database) and Render (hosting)</b> – store your profile and conversation securely.</li>
  <li><b>OpenStreetMap Nominatim</b> – converts your place of birth into map coordinates (only the place name is sent).</li>
  <li><b>Prokerala Astrology API</b> – may be used for additional chart calculations (birth date, time and coordinates only).</li>
</ul>

<h2>Data retention</h2>
<p>We keep your profile and conversation history while you use the service so we can give you consistent guidance.
You can ask us to delete it at any time (see below).</p>

<h2 id="data-deletion">Your choices and data deletion</h2>
<ul>
  <li>To <b>change</b> your birth details, send <b>RESET</b> in the WhatsApp chat.</li>
  <li>To <b>delete</b> all your data, email <a href="mailto:{CONTACT_EMAIL}?subject=Delete%20my%20data">{CONTACT_EMAIL}</a>
      with the subject "Delete my data" and your WhatsApp number. We will delete your profile, chart and conversation
      history within 30 days and confirm by email.</li>
  <li>You can stop using the service at any time by no longer messaging us or by blocking the number.</li>
</ul>

<h2>Security</h2>
<p>Data is sent over encrypted connections (HTTPS/TLS) and stored in access-controlled systems. No method of
transmission or storage is completely secure, but we take reasonable measures to protect your information.</p>

<h2>Important note</h2>
<p>Astrological guidance is for personal reflection and is not a substitute for medical, legal, financial or other
professional advice.</p>

<h2>Children</h2>
<p>The service is not intended for children under 13, and we do not knowingly collect their information.</p>

<h2>Changes and contact</h2>
<p>We may update this policy; the "Last updated" date shows the latest version. Questions? Email
<a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
</main></body>
</html>"""
