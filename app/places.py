"""Offline lookup of Indian birthplaces - no internet map service needed.

Data: GeoNames (https://www.geonames.org), licensed CC BY 4.0. ~549,000 Indian cities, towns and villages
with old/alternate names (Bangalore -> Bengaluru, Gulbarga -> Kalaburagi, Calcutta -> Kolkata...).
app/places_india.tsv.gz is built by tools/build_places.py. On first use it is turned into a small SQLite
index in data/ so lookups are instant and use almost no memory.
"""
import difflib
import gzip
import logging
import re
import sqlite3
import threading
import unicodedata
from pathlib import Path

log = logging.getLogger("astrovinod")

_SRC = Path(__file__).with_name("places_india.tsv.gz")
_DB = Path(__file__).resolve().parent.parent / "data" / "places_india.sqlite"
_build_lock = threading.Lock()
_local = threading.local()

STATES = {
    "01": "Andaman and Nicobar", "02": "Andhra Pradesh", "03": "Assam", "05": "Chandigarh", "07": "Delhi",
    "09": "Gujarat", "10": "Haryana", "11": "Himachal Pradesh", "12": "Jammu and Kashmir", "13": "Kerala",
    "14": "Lakshadweep", "16": "Maharashtra", "17": "Manipur", "18": "Meghalaya", "19": "Karnataka",
    "20": "Nagaland", "21": "Odisha", "22": "Puducherry", "23": "Punjab", "24": "Rajasthan", "25": "Tamil Nadu",
    "26": "Tripura", "28": "West Bengal", "29": "Sikkim", "30": "Arunachal Pradesh", "31": "Mizoram",
    "33": "Goa", "34": "Bihar", "35": "Madhya Pradesh", "36": "Uttar Pradesh", "37": "Chhattisgarh",
    "38": "Jharkhand", "39": "Uttarakhand", "40": "Telangana", "41": "Ladakh",
    "52": "Dadra and Nagar Haveli and Daman and Diu",
}
_STATE_ALIASES = {
    "andaman": "01", "andaman and nicobar islands": "01", "ap": "02", "andhra": "02", "orissa": "21", "odisa": "21",
    "pondicherry": "22", "pondy": "22", "tn": "25", "tamilnadu": "25", "wb": "28", "bengal": "28",
    "chattisgarh": "37", "chhatisgarh": "37", "chattishgarh": "37", "cg": "37", "jk": "12", "j and k": "12",
    "kashmir": "12", "jammu": "12", "jammu kashmir": "12", "mp": "35", "up": "36", "ka": "19", "karnatak": "19",
    "telengana": "40", "ts": "40", "tg": "40", "uttaranchal": "39", "hp": "11", "maharastra": "16", "mh": "16",
    "gujrat": "09", "rajastan": "24", "new delhi": "07", "nct": "07", "daman": "52", "diu": "52",
}
_COUNTRY = {"india", "bharat", "ind", "hindustan", "republic of india"}
# Another country named -> not an Indian place (left to the online map services).
_FOREIGN = {
    "nepal", "pakistan", "bangladesh", "sri lanka", "srilanka", "bhutan", "myanmar", "burma", "china", "maldives",
    "usa", "us", "u s", "u s a", "united states", "united states of america", "america", "uk", "u k", "united kingdom",
    "england", "scotland", "wales", "ireland", "canada", "australia", "new zealand", "uae", "u a e",
    "united arab emirates", "dubai", "abu dhabi", "saudi arabia", "saudi", "qatar", "kuwait", "oman", "bahrain",
    "singapore", "malaysia", "indonesia", "thailand", "japan", "korea", "south korea", "germany", "france", "italy",
    "spain", "netherlands", "switzerland", "sweden", "norway", "russia", "south africa", "kenya", "mauritius",
    "fiji", "trinidad", "guyana", "hong kong", "philippines", "vietnam",
}
_SKIP_WORDS ={"city", "town", "village", "district", "dist", "taluk", "taluka", "tehsil", "mandal", "urban", "rural"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


_STATE_KEYS = {normalize(n): c for c, n in STATES.items()} | _STATE_ALIASES


def _build() -> None:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DB.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript("""
        CREATE TABLE places (id INTEGER PRIMARY KEY, name TEXT, state TEXT, lat REAL, lon REAL, pop INTEGER);
        CREATE TABLE keys (key TEXT, place INTEGER);
    """)
    with gzip.open(_SRC, "rt", encoding="utf-8") as f:
        places, keys = [], []
        for i, line in enumerate(f):
            name, state, lat, lon, pop, alts = line.rstrip("\n").split("\t")
            places.append((i, name, state, float(lat), float(lon), int(pop or 0)))
            for k in {normalize(name), *(normalize(a) for a in alts.split("|") if a)}:
                if k:
                    keys.append((k, i))
        con.executemany("INSERT INTO places VALUES (?,?,?,?,?,?)", places)
        con.executemany("INSERT INTO keys VALUES (?,?)", keys)
    con.execute("CREATE INDEX keys_key ON keys(key)")
    con.commit()
    con.close()
    tmp.replace(_DB)
    log.info("Built offline places index: %d places, %d names", len(places), len(keys))


def ensure_db() -> None:
    with _build_lock:
        if not _DB.exists() or _DB.stat().st_mtime < _SRC.stat().st_mtime:
            _build()


def _con() -> sqlite3.Connection:
    con = getattr(_local, "con", None)
    if con is None:
        ensure_db()
        con = _local.con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    return con


def _exact(key: str) -> list[tuple]:
    return _con().execute(
        "SELECT p.name, p.state, p.lat, p.lon, p.pop FROM keys k JOIN places p ON p.id = k.place "
        "WHERE k.key = ? GROUP BY p.id", (key,)).fetchall()


def _fuzzy(key: str) -> list[tuple]:
    """Close spellings (bhopalpatam -> Bhopalpatnam). Only keys sharing the first 3 letters are compared."""
    if len(key) < 5:
        return []
    cands = [r[0] for r in _con().execute(
        "SELECT DISTINCT key FROM keys WHERE key >= ? AND key < ?", (key[:3], key[:3] + "\x7f"))]
    best = difflib.get_close_matches(key, cands, n=3, cutoff=0.86)
    return [row for k in best for row in _exact(k)]


def _peel(words: list[str], states: set, flags: dict) -> list[str]:
    """Remove trailing state/country words: 'bangalore india' -> 'bangalore'."""
    changed = True
    while changed and len(words) > 1:
        changed = False
        for n in (4, 3, 2, 1):
            if len(words) > n:
                tail = " ".join(words[-n:])
                if tail in _COUNTRY:
                    flags["india"] = True
                elif tail in _STATE_KEYS:
                    states.add(_STATE_KEYS[tail])
                else:
                    continue
                words, changed = words[:-n], True
                break
    return words


def lookup(place: str) -> dict | None:
    """Find an Indian birthplace offline. None if not found or the text names another country.
    The result's "strong" is False when the match is uncertain (spelling guess, only part of the text matched,
    or a tiny village with no state/country given) - the caller should prefer an online map result then."""
    parts = [normalize(p) for p in re.split(r"[,;/\n]+", place or "")]
    parts = [p for p in parts if p]
    if not parts:
        return None
    if any(p in _FOREIGN for p in parts) or any(
            " ".join(parts[0].split()[-n:]) in _FOREIGN for n in (1, 2, 3) if len(parts[0].split()) > n):
        return None
    states: set[str] = set()
    flags = {"india": False}
    others = []
    for p in parts[1:]:
        if p in _COUNTRY:
            flags["india"] = True
        elif p in _STATE_KEYS:
            states.add(_STATE_KEYS[p])
        else:
            others.append(p)
    # Peel "india"/state words off the end, unless the whole phrase is itself a place ("new delhi").
    words = parts[0].split() if _exact(parts[0]) else _peel(parts[0].split(), states, flags)
    words = [w for w in words if w not in _SKIP_WORDS] or words
    first = " ".join(words)

    # Something like "London, UK" or "Hyderabad, Pakistan": the extra part is not Indian -> leave it to online maps.
    if others and not flags["india"] and not states and not any(_exact(o) for o in others):
        return None

    def in_states(rows: list[tuple]) -> list[tuple]:
        return [r for r in rows if r[1] in states] if states else rows

    # Town names come first, district/state after: "bhopalpatam bijapur" is Bhopalpatnam (in Bijapur district).
    exact, rows = True, in_states(_exact(first))
    if not rows and len(words) > 1:
        exact = False
        for n in range(len(words) - 1, 0, -1):  # leading words: "kolar gold" -> ... -> "kolar"
            rows = in_states(_exact(" ".join(words[:n])))
            if rows:
                break
    if not rows or (not exact and len(words) > 1):
        guess = in_states(_fuzzy(first)) or (in_states(_fuzzy(words[0])) if len(words) > 1 else [])
        if guess:
            exact, rows = False, guess
    if not rows and len(words) > 1:  # any other piece, e.g. only the district is spelled right
        exact = False
        for n in range(len(words) - 1, 0, -1):
            rows = next((r for i in range(1, len(words) - n + 1)
                         if (r := in_states(_exact(" ".join(words[i:i + n]))))), [])
            if rows:
                break
    if not rows:
        return None
    name, state, lat, lon, pop = max(rows, key=lambda r: r[4])
    label = ", ".join(x for x in (name, STATES.get(state, ""), "India") if x)
    strong = exact and (pop > 0 or bool(states) or flags["india"])
    return {"latitude": lat, "longitude": lon, "resolved_place": label, "strong": strong}
