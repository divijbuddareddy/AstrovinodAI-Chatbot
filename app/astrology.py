"""Birthplace geocoding, timezone resolution and Prokerala kundli lookup."""
import json
import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from timezonefinder import TimezoneFinder

from . import config

log = logging.getLogger("astrovinod")
_tf = TimezoneFinder()
_token = {"value": "", "expires": 0.0}
_token_lock = threading.Lock()


class BirthplaceNotFound(Exception):
    pass


def geocode(place: str) -> dict:
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "jsonv2", "limit": 1},
        headers={"User-Agent": config.NOMINATIM_USER_AGENT},
        timeout=20,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise BirthplaceNotFound(place)
    top = results[0]
    return {"latitude": float(top["lat"]), "longitude": float(top["lon"]), "resolved_place": top.get("display_name", place)}


def birth_datetime(dob: str, birth_time: str, lat: float, lon: float) -> tuple[str, str]:
    """Return (IANA timezone, ISO-8601 datetime with the correct historical UTC offset)."""
    tz_name = _tf.timezone_at(lng=lon, lat=lat) or "Asia/Kolkata"
    y, m, d = (int(x) for x in dob.split("-"))
    hh, mm = (int(x) for x in birth_time.split(":"))
    local = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tz_name))
    return tz_name, local.isoformat()


def _prokerala_token() -> str:
    with _token_lock:
        if _token["value"] and time.time() < _token["expires"] - 60:
            return _token["value"]
        resp = requests.post(
            "https://api.prokerala.com/token",
            data={
                "grant_type": "client_credentials",
                "client_id": config.PROKERALA_CLIENT_ID,
                "client_secret": config.PROKERALA_CLIENT_SECRET,
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        _token["value"] = body["access_token"]
        _token["expires"] = time.time() + int(body.get("expires_in", 3600))
        return _token["value"]


def prokerala_extras(lat: float, lon: float, iso_datetime: str) -> dict | None:
    """Optional enrichment (yogas, doshas...) from Prokerala. Returns None if the API fails
    (e.g. no credits) - the local engine in vedic.py is always the primary chart source."""
    try:
        data = kundli(lat, lon, iso_datetime)
    except Exception as exc:  # noqa: BLE001
        log.warning("Prokerala unavailable, using local engine only: %s", str(exc)[:200])
        return None
    # Dashas come from the local engine; drop Prokerala's (very large) copy.
    data = {k: v for k, v in data.items() if "dasha" not in k.lower()}
    return data if len(json.dumps(data)) < 30000 else None


def kundli(lat: float, lon: float, iso_datetime: str) -> dict:
    resp = requests.get(
        "https://api.prokerala.com/v2/astrology/kundli/advanced",
        params={
            "ayanamsa": config.PROKERALA_AYANAMSA,
            "coordinates": f"{lat},{lon}",
            "datetime": iso_datetime,
            "la": "en",
        },
        headers={"Authorization": f"Bearer {_prokerala_token()}"},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Prokerala error ({resp.status_code}): {resp.text[:500]}")
    return resp.json().get("data", resp.json())
