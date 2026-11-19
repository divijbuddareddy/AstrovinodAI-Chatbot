"""Birthplace geocoding, timezone resolution and Prokerala kundli lookup."""
import functools
import json
import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from timezonefinder import TimezoneFinder

from . import config, places

log = logging.getLogger("astrovinod")
_tf = TimezoneFinder()
_token = {"value": "", "expires": 0.0}
_token_lock = threading.Lock()


class BirthplaceNotFound(Exception):
    pass


class GeocodingUnavailable(Exception):
    """Every map service failed (network error, blocked or rate-limited) - not the user's fault."""


def _nominatim(place: str) -> dict | None:
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        # settlements only (not shops/banks named after the town), names in English
        params={"q": place, "format": "jsonv2", "limit": 1, "featureType": "settlement", "accept-language": "en"},
        headers={"User-Agent": config.NOMINATIM_USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    top = results[0]
    name = ", ".join(p.strip() for p in top.get("display_name", place).split(",") if not p.strip().isdigit())
    return {"latitude": float(top["lat"]), "longitude": float(top["lon"]), "resolved_place": name}


def _photon(place: str) -> dict | None:
    resp = requests.get(
        "https://photon.komoot.io/api/",
        params={"q": place, "limit": 1, "lang": "en", "osm_tag": "place"},  # towns/villages, not shops
        headers={"User-Agent": config.NOMINATIM_USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    features = resp.json().get("features") or []
    if not features:
        return None
    p, (lon, lat) = features[0]["properties"], features[0]["geometry"]["coordinates"]
    name = ", ".join(dict.fromkeys(x for x in (p.get("name"), p.get("city"), p.get("state"), p.get("country")) if x))
    return {"latitude": float(lat), "longitude": float(lon), "resolved_place": name or place}


def _open_meteo(place: str) -> dict | None:
    parts = [x.strip() for x in place.split(",") if x.strip()]
    if not parts:
        return None
    hints = {x.lower() for x in parts[1:]}

    def search(**extra) -> list[dict]:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": parts[0], "count": 10, "language": "en", **extra},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("results") or []

    # Most clients are Indian: look in India first unless they named another country.
    results = search(countryCode="IN") if (not hints or "india" in hints) else []
    if not results and "india" not in hints:
        results = search()
    if not results:
        return None

    aliases = {"uae": "ae", "usa": "us", "america": "us", "uk": "gb", "england": "gb", "britain": "gb"}
    codes = {aliases.get(h, h) for h in hints}

    def score(r: dict) -> int:  # prefer the state/country the user typed, then India
        s = 2 * sum(1 for k in ("admin1", "country") if str(r.get(k, "")).lower() in hints)
        s += 2 if str(r.get("country_code", "")).lower() in codes else 0
        return s + (1 if r.get("country_code") == "IN" else 0)

    top = max(results, key=score)
    if hints and score(top) < 2:  # user named a state/country and no result is there -> wrong town
        return None
    name = ", ".join(x for x in (top.get("name"), top.get("admin1"), top.get("country")) if x)
    return {"latitude": float(top["latitude"]), "longitude": float(top["longitude"]), "resolved_place": name}


def geocode(place: str) -> dict:
    """Find a birthplace on the map, falling back to other free services if one fails.
    Results are cached, so the 1,000th "Bengaluru" never touches the map services."""
    return dict(_geocode_cached(" ".join(place.lower().replace(",", ", ").split())))


@functools.lru_cache(maxsize=20000)
def _geocode_cached(place: str) -> dict:  # exceptions are not cached, so failures get retried next time
    local = None
    try:
        local = places.lookup(place)  # built-in list of Indian places: no internet needed
    except Exception:
        log.exception("Offline place lookup failed for %r", place)
    if local and local.pop("strong"):
        return local
    # Not in the built-in list, or only an uncertain match there: ask the online map services too.
    errors = 0
    for service in (_nominatim, _photon, _open_meteo):
        try:
            found = service(place)
        except Exception as exc:  # blocked, rate-limited, timeout, bad JSON...
            errors += 1
            log.warning("Geocoder %s failed for %r: %s", service.__name__, place, str(exc)[:200])
            continue
        if found:
            return found
    if local:
        return local
    if errors == 3:
        raise GeocodingUnavailable(place)
    raise BirthplaceNotFound(place)


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
