"""Local Vedic astrology engine (no API credits needed).

Uses NASA JPL DE421 ephemeris via Skyfield (valid 1900-2053) for planetary positions,
Lahiri (Chitrapaksha) ayanamsa, mean lunar node for Rahu/Ketu, whole-sign houses and
Vimshottari dasha - the standard Parashari setup used by most Indian astrologers.
"""
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from skyfield import almanac
from skyfield.api import Loader, wgs84
from skyfield.framelib import ecliptic_frame

_DATA = Path(__file__).resolve().parent.parent / "data"
_load = Loader(str(_DATA), verbose=False)
ts = _load.timescale(builtin=True)
eph = _load("de421.bsp")
_earth = eph["earth"]

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars",
              "Jupiter", "Saturn", "Saturn", "Jupiter"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya",
              "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
              "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
              "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
DASHA_ORDER = [("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
               ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)]
DASHA_YEARS = dict(DASHA_ORDER)
TITHIS = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami",
          "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi"]
YOGAS = ["Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma", "Dhriti", "Shula",
         "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyan",
         "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"]
MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti (Bhadra)"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_LORDS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]  # Monday=0
HORA_SEQUENCE = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
RAHU_KAAL_SEGMENT = [2, 7, 5, 6, 4, 3, 8]  # 1-based eighth of daytime, Monday=0
_BODIES = {"Sun": "sun", "Moon": "moon", "Mars": "mars", "Mercury": "mercury",
           "Jupiter": "jupiter barycenter", "Venus": "venus", "Saturn": "saturn barycenter"}
PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
NAK_LEN = 360 / 27
YEAR_DAYS = 365.25


# ---------------------------------------------------------------- core astronomy
def _T(t) -> float:
    return (t.tt - 2451545.0) / 36525.0


def _precession(T: float) -> float:
    return (5028.796195 * T + 1.1054348 * T * T) / 3600.0


_LAHIRI_T0 = (2435553.5 - 2451545.0) / 36525.0  # Lahiri reference epoch (Swiss Ephemeris definition)


def ayanamsa(t) -> float:
    return 23.245524743 + _precession(_T(t)) - _precession(_LAHIRI_T0)


def _tropical(t, name: str) -> float:
    lat, lon, _ = _earth.at(t).observe(eph[_BODIES[name]]).apparent().frame_latlon(ecliptic_frame)
    return lon.degrees % 360


def _mean_node(t) -> float:
    T = _T(t)
    return (125.04452 - 1934.136261 * T + 0.0020708 * T * T + T ** 3 / 450000.0) % 360


def _ascendant_tropical(t, lat: float, lon: float) -> float:
    T = _T(t)
    eps = math.radians(23.4392911 - 0.0130042 * T)
    ramc = math.radians((t.gast * 15.0 + lon) % 360)
    phi = math.radians(lat)
    asc = math.atan2(math.cos(ramc), -(math.sin(eps) * math.tan(phi) + math.cos(eps) * math.sin(ramc)))
    return math.degrees(asc) % 360


def sidereal_positions(t) -> dict[str, tuple[float, bool]]:
    """{planet: (sidereal longitude, is_retrograde)}"""
    ay = ayanamsa(t)
    t_next = ts.tt_jd(t.tt + 0.5)
    out = {}
    for name in _BODIES:
        l1, l2 = _tropical(t, name), _tropical(t_next, name)
        speed = ((l2 - l1 + 540) % 360) - 180
        out[name] = ((l1 - ay) % 360, speed < 0 and name not in ("Sun", "Moon"))
    rahu = (_mean_node(t) - ay) % 360
    out["Rahu"] = (rahu, True)
    out["Ketu"] = ((rahu + 180) % 360, True)
    return out


def _sign_idx(lon: float) -> int:
    return int(lon // 30) % 12


def describe(lon: float) -> dict:
    nak = int(lon // NAK_LEN) % 27
    return {
        "sign": SIGNS[_sign_idx(lon)],
        "degree": round(lon % 30, 2),
        "nakshatra": NAKSHATRAS[nak],
        "pada": int((lon % NAK_LEN) // (NAK_LEN / 4)) + 1,
        "nakshatra_lord": DASHA_ORDER[nak % 9][0],
    }


def _house(from_sign: int, lon: float) -> int:
    return (_sign_idx(lon) - from_sign) % 12 + 1


def _sun_times(day: date, tz_name: str, lat: float, lon: float):
    tz = ZoneInfo(tz_name)
    observer = _earth + wgs84.latlon(lat, lon)
    t0 = ts.from_datetime(datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz))
    t1 = ts.from_datetime(datetime(day.year, day.month, day.day, 23, 59, tzinfo=tz))
    rises, _ = almanac.find_risings(observer, eph["sun"], t0, t1)
    sets, _ = almanac.find_settings(observer, eph["sun"], t0, t1)
    rise = rises[0] if len(rises) else None
    sset = sets[-1] if len(sets) else None
    return rise, sset


def _tithi(sun_lon: float, moon_lon: float) -> dict:
    elong = (moon_lon - sun_lon) % 360
    n = int(elong // 12)  # 0..29
    paksha = "Shukla" if n < 15 else "Krishna"
    name = "Purnima" if n == 14 else "Amavasya" if n == 29 else TITHIS[n % 15]
    return {"number": n + 1, "paksha": paksha, "name": f"{paksha} {name}"}


def _yoga_karana(sun_lon: float, moon_lon: float) -> tuple[str, str]:
    yoga = YOGAS[int(((sun_lon + moon_lon) % 360) // NAK_LEN) % 27]
    k = int(((moon_lon - sun_lon) % 360) // 6)  # 0..59
    if k == 0:
        karana = "Kimstughna"
    elif k <= 56:
        karana = MOVABLE_KARANAS[(k - 1) % 7]
    else:
        karana = ["Shakuni", "Chatushpada", "Naga"][k - 57]
    return yoga, karana


def birth_panchanga(local: datetime, lat: float, lon: float, pos: dict) -> dict:
    """The five limbs (Tithi, Vara, Nakshatra, Yoga, Karana) at the moment of birth.
    Vedic Vara runs sunrise to sunrise, so a birth before sunrise belongs to the previous weekday."""
    tz_name = local.tzinfo.key
    rise, _ = _sun_times(local.date(), tz_name, lat, lon)
    wd = local.weekday()
    if rise is not None and local < rise.astimezone(local.tzinfo):
        wd = (wd - 1) % 7
    sun, moon = pos["Sun"][0], pos["Moon"][0]
    yoga, karana = _yoga_karana(sun, moon)
    nak = describe(moon)
    return {
        "tithi": _tithi(sun, moon),
        "vara": {"weekday": WEEKDAYS[wd], "lord": WEEKDAY_LORDS[wd]},
        "nakshatra": {"name": nak["nakshatra"], "pada": nak["pada"], "lord": nak["nakshatra_lord"]},
        "yoga": yoga,
        "karana": karana,
        "sunrise_on_birth_day": rise.astimezone(local.tzinfo).strftime("%I:%M %p") if rise is not None else None,
    }


# ---------------------------------------------------------------- natal chart
def natal_chart(dob: str, birth_time: str, tz_name: str, lat: float, lon: float) -> dict:
    y, m, d = (int(x) for x in dob.split("-"))
    hh, mm = (int(x) for x in birth_time.split(":"))
    local = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tz_name))
    t = ts.from_datetime(local)

    asc = (_ascendant_tropical(t, lat, lon) - ayanamsa(t)) % 360
    asc_sign = _sign_idx(asc)
    pos = sidereal_positions(t)

    planets = {}
    for name in PLANETS:
        plon, retro = pos[name]
        info = describe(plon)
        info["house"] = _house(asc_sign, plon)
        info["sign_lord"] = SIGN_LORDS[_sign_idx(plon)]
        if retro and name not in ("Rahu", "Ketu"):
            info["retrograde"] = True
        planets[name] = info

    houses = {}
    for h in range(1, 13):
        sign = (asc_sign + h - 1) % 12
        houses[str(h)] = {"sign": SIGNS[sign], "lord": SIGN_LORDS[sign],
                          "occupants": [p for p in PLANETS if planets[p]["house"] == h]}

    moon_lon = pos["Moon"][0]
    return {
        "engine": "AstroVinod local engine (JPL DE421, Lahiri ayanamsa, mean node, whole-sign houses)",
        "birth": {"local_datetime": local.isoformat(), "timezone": tz_name, "latitude": lat, "longitude": lon},
        "ayanamsa_lahiri": round(ayanamsa(t), 4),
        "lagna": {**describe(asc), "lord": SIGN_LORDS[asc_sign]},
        "moon_sign_rashi": SIGNS[_sign_idx(moon_lon)],
        "janma_nakshatra": describe(moon_lon)["nakshatra"],
        "sun_sign_sidereal": SIGNS[_sign_idx(pos["Sun"][0])],
        "birth_panchanga": birth_panchanga(local, lat, lon, pos),
        "planets": planets,
        "houses": houses,
        "vimshottari_dasha": vimshottari(moon_lon, local),
    }


def vimshottari(moon_lon: float, birth: datetime) -> list[dict]:
    nak = int(moon_lon // NAK_LEN) % 27
    elapsed = (moon_lon % NAK_LEN) / NAK_LEN
    start_i = nak % 9
    first_years = DASHA_ORDER[start_i][1]
    cur = birth - timedelta(days=elapsed * first_years * YEAR_DAYS)
    periods = []
    for k in range(9):
        lord, years = DASHA_ORDER[(start_i + k) % 9]
        md_end = cur + timedelta(days=years * YEAR_DAYS)
        ads, ac = [], cur
        for j in range(9):
            alord, ayears = DASHA_ORDER[(start_i + k + j) % 9]
            ae = ac + timedelta(days=years * ayears / 120 * YEAR_DAYS)
            ads.append({"lord": alord, "start": ac.date().isoformat(), "end": ae.date().isoformat()})
            ac = ae
        periods.append({"lord": lord, "start": cur.date().isoformat(), "end": md_end.date().isoformat(), "antardasha": ads})
        cur = md_end
    return periods


def running_dasha(chart: dict, on: date) -> dict:
    iso = on.isoformat()
    for md in chart.get("vimshottari_dasha", []):
        if md["start"] <= iso < md["end"]:
            for ad in md["antardasha"]:
                if ad["start"] <= iso < ad["end"]:
                    # Pratyantardasha computed on the fly
                    a_start, a_end = date.fromisoformat(ad["start"]), date.fromisoformat(ad["end"])
                    span = (a_end - a_start).days
                    idx = [l for l, _ in DASHA_ORDER].index(ad["lord"])
                    pc = a_start
                    for j in range(9):
                        plord, pyears = DASHA_ORDER[(idx + j) % 9]
                        pe = pc + timedelta(days=span * pyears / 120)
                        if pc <= on < pe:
                            return {"mahadasha": {k: md[k] for k in ("lord", "start", "end")},
                                    "antardasha": ad,
                                    "pratyantardasha": {"lord": plord, "start": pc.isoformat(), "end": pe.isoformat()}}
                        pc = pe
                    return {"mahadasha": {k: md[k] for k in ("lord", "start", "end")}, "antardasha": ad}
    return {}


# ---------------------------------------------------------------- transits
def _natal_refs(chart: dict) -> tuple[int, int]:
    return SIGNS.index(chart["lagna"]["sign"]), SIGNS.index(chart["moon_sign_rashi"])


def transit_snapshot(chart: dict, when: datetime) -> dict:
    lagna_i, moon_i = _natal_refs(chart)
    pos = sidereal_positions(ts.from_datetime(when))
    out = {}
    for name in PLANETS:
        plon, retro = pos[name]
        info = describe(plon)
        info["house_from_lagna"] = _house(lagna_i, plon)
        info["house_from_moon"] = _house(moon_i, plon)
        if retro and name not in ("Rahu", "Ketu"):
            info["retrograde"] = True
        out[name] = info
    sat_from_moon = out["Saturn"]["house_from_moon"]
    out["notes"] = {
        "sade_sati": sat_from_moon in (12, 1, 2),
        "sade_sati_phase": {12: "rising (1st phase)", 1: "peak (2nd phase)", 2: "setting (3rd phase)"}.get(sat_from_moon, "none"),
        "ashtama_shani": sat_from_moon == 8,
        "kantaka_shani": sat_from_moon in (4, 7, 10),
    }
    return out


def period_transits(chart: dict, start: date, end: date, tz_name: str) -> dict:
    """Sign changes and retrograde stations of planets, plus daily Moon transit, between start and end (inclusive)."""
    tz = ZoneInfo(tz_name)
    _, moon_i = _natal_refs(chart)
    events, moon_days = [], []
    prev = None
    day = start
    while day <= end:
        when = datetime(day.year, day.month, day.day, 6, 0, tzinfo=tz)
        pos = sidereal_positions(ts.from_datetime(when))
        moon_lon = pos["Moon"][0]
        house = _house(moon_i, moon_lon)
        moon_days.append({
            "date": day.isoformat(), "weekday": day.strftime("%A"),
            "moon_sign": SIGNS[_sign_idx(moon_lon)], "moon_nakshatra": describe(moon_lon)["nakshatra"],
            "moon_house_from_natal_moon": house,
            **({"chandrashtama": True} if house == 8 else {}),
        })
        if prev:
            for name in PLANETS:
                if name == "Moon":
                    continue
                s0, s1 = _sign_idx(prev[name][0]), _sign_idx(pos[name][0])
                if s0 != s1:
                    events.append({"date": day.isoformat(), "event": f"{name} enters {SIGNS[s1]}"})
                if prev[name][1] != pos[name][1] and name not in ("Rahu", "Ketu"):
                    events.append({"date": day.isoformat(),
                                   "event": f"{name} turns {'retrograde' if pos[name][1] else 'direct'}"})
        prev = pos
        day += timedelta(days=1)
    return {"planet_events": events, "daily_moon": moon_days}


def daily_panchang(day: date, tz_name: str, lat: float, lon: float) -> dict:
    tz = ZoneInfo(tz_name)
    rise_t, set_t = _sun_times(day, tz_name, lat, lon)
    if rise_t is None or set_t is None:
        return {}
    sunrise = rise_t.astimezone(tz)
    sunset = set_t.astimezone(tz)

    pos = sidereal_positions(rise_t)
    tithi = _tithi(pos["Sun"][0], pos["Moon"][0])["name"]
    yoga, karana = _yoga_karana(pos["Sun"][0], pos["Moon"][0])

    daylen = sunset - sunrise
    eighth = daylen / 8
    seg = RAHU_KAAL_SEGMENT[day.weekday()] - 1
    muhurta = daylen / 15
    hora_len = daylen / 12
    lord0 = WEEKDAY_LORDS[day.weekday()]
    seq_start = HORA_SEQUENCE.index(lord0)
    fmt = "%I:%M %p"
    horas = []
    for i in range(12):
        s = sunrise + hora_len * i
        horas.append({"lord": HORA_SEQUENCE[(seq_start + i) % 7], "from": s.strftime(fmt), "to": (s + hora_len).strftime(fmt)})

    return {
        "date": day.isoformat(), "weekday": day.strftime("%A"), "weekday_lord": lord0,
        "sunrise": sunrise.strftime(fmt), "sunset": sunset.strftime(fmt),
        "tithi": tithi, "yoga": yoga, "karana": karana,
        "moon_sign": SIGNS[_sign_idx(pos["Moon"][0])],
        "moon_nakshatra": describe(pos["Moon"][0])["nakshatra"],
        "rahu_kaal": {"from": (sunrise + eighth * seg).strftime(fmt), "to": (sunrise + eighth * (seg + 1)).strftime(fmt)},
        "abhijit_muhurat": {"from": (sunrise + muhurta * 7).strftime(fmt), "to": (sunrise + muhurta * 8).strftime(fmt)},
        "day_horas": horas,
        "location_used": f"{lat:.2f},{lon:.2f} ({tz_name})",
    }
