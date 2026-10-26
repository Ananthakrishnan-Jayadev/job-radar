"""Turn each source's location data into `Location` objects.

Two entry points:

- `from_parts(city, region, country, ...)` for sources with structured fields
  (Ashby address, Workable, Recruitee, SmartRecruiters, Rippling, BambooHR).
- `parse_text(text, ...)` for free text ("Toronto, ON", "TORONTO-Ontario-Canada",
  "Remote (Canada)", "New York City, NY; San Francisco, CA").

`canadian_company=True` lets ambiguous city names (London, Waterloo, Hamilton...)
resolve to their Canadian city; otherwise they stay without a country.
All forms are listed in docs/04-canadian-sources.md.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .models import Location

# --- reference data ---------------------------------------------------------

PROVINCE_CODES = {"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"}

# Keys are folded (lowercase, no accents, no punctuation).
PROVINCE_NAMES = {
    "ontario": "ON",
    "ont": "ON",
    "quebec": "QC",
    "province of quebec": "QC",
    "british columbia": "BC",
    "colombie britannique": "BC",
    "alberta": "AB",
    "manitoba": "MB",
    "saskatchewan": "SK",
    "nova scotia": "NS",
    "nouvelle ecosse": "NS",
    "new brunswick": "NB",
    "nouveau brunswick": "NB",
    "newfoundland and labrador": "NL",
    "newfoundland": "NL",
    "terre neuve et labrador": "NL",
    "prince edward island": "PE",
    "ile du prince edouard": "PE",
    "pei": "PE",
    "yukon": "YT",
    "northwest territories": "NT",
    "territoires du nord ouest": "NT",
    "nunavut": "NU",
}

# Canadian cities that are not commonly a city name elsewhere.
CITIES = {
    # Ontario
    "toronto": "ON", "north york": "ON", "etobicoke": "ON", "mississauga": "ON",
    "brampton": "ON", "markham": "ON", "vaughan": "ON", "richmond hill": "ON",
    "oakville": "ON", "burlington": "ON", "kitchener": "ON", "guelph": "ON",
    "ottawa": "ON", "kanata": "ON", "nepean": "ON", "barrie": "ON", "oshawa": "ON",
    "whitby": "ON", "pickering": "ON", "ajax": "ON", "milton": "ON",
    "st catharines": "ON", "saint catharines": "ON", "sudbury": "ON",
    "greater sudbury": "ON", "thunder bay": "ON", "thornhill": "ON",
    "newmarket": "ON", "brantford": "ON", "sarnia": "ON", "belleville": "ON",
    "north bay": "ON", "niagara on the lake": "ON", "woodbridge": "ON",
    "bolton": "ON", "stoney creek": "ON",
    # Quebec
    "montreal": "QC", "laval": "QC", "gatineau": "QC", "longueuil": "QC",
    "sherbrooke": "QC", "trois rivieres": "QC", "quebec city": "QC",
    "ville de quebec": "QC", "levis": "QC", "saguenay": "QC",
    # British Columbia
    "vancouver": "BC", "burnaby": "BC", "surrey": "BC", "coquitlam": "BC",
    "kelowna": "BC", "kamloops": "BC", "nanaimo": "BC", "abbotsford": "BC",
    "north vancouver": "BC", "new westminster": "BC",
    # Prairies
    "calgary": "AB", "edmonton": "AB", "red deer": "AB", "lethbridge": "AB",
    "winnipeg": "MB", "regina": "SK", "saskatoon": "SK",
    # Atlantic and north
    "dartmouth": "NS", "fredericton": "NB", "moncton": "NB", "saint john": "NB",
    "st johns": "NL", "charlottetown": "PE", "whitehorse": "YT",
    "yellowknife": "NT", "iqaluit": "NU",
}

# Names shared with places outside Canada: Canadian only when the country or
# province says so, or the company is Canadian.
AMBIGUOUS_CITIES = {
    "london": "ON", "waterloo": "ON", "hamilton": "ON", "cambridge": "ON",
    "kingston": "ON", "windsor": "ON", "peterborough": "ON", "scarborough": "ON",
    "niagara falls": "ON", "aurora": "ON", "concord": "ON", "cornwall": "ON",
    "stratford": "ON", "sault ste marie": "ON", "richmond": "BC",
    "victoria": "BC", "halifax": "NS",
}

# Region names that stand for a city.
CITY_ALIASES = {
    "gta": ("Toronto", "ON"),
    "greater toronto area": ("Toronto", "ON"),
    "greater toronto": ("Toronto", "ON"),
    "toronto area": ("Toronto", "ON"),
    "kw": ("Kitchener", "ON"),
    "kitchener waterloo": ("Kitchener", "ON"),
    "waterloo region": ("Kitchener", "ON"),
    "ncr": ("Ottawa", "ON"),
    "national capital region": ("Ottawa", "ON"),
    "greater vancouver": ("Vancouver", "BC"),
    "metro vancouver": ("Vancouver", "BC"),
    "greater montreal": ("Montreal", "QC"),
}

# Big foreign tech hubs, so "Amsterdam, NL" isn't read as Newfoundland.
FOREIGN_CITIES = {
    "amsterdam", "berlin", "munich", "paris", "dublin", "madrid", "barcelona",
    "lisbon", "warsaw", "krakow", "prague", "vienna", "zurich", "stockholm",
    "copenhagen", "oslo", "helsinki", "sofia", "bucharest", "tel aviv",
    "bangalore", "bengaluru", "hyderabad", "pune", "chennai", "mumbai",
    "new delhi", "gurgaon", "gurugram", "noida", "singapore", "sydney",
    "melbourne", "tokyo", "seoul", "manila", "mexico city", "sao paulo",
    "buenos aires", "bogota",
}

COUNTRY_NAMES = {
    "canada": "CA", "can": "CA", "united states": "US", "united states of america": "US",
    "usa": "US", "us": "US", "u s": "US", "u s a": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "u k": "GB", "great britain": "GB",
    "england": "GB", "scotland": "GB", "wales": "GB", "ireland": "IE",
    "germany": "DE", "france": "FR", "netherlands": "NL", "the netherlands": "NL",
    "belgium": "BE", "spain": "ES", "portugal": "PT", "italy": "IT", "poland": "PL",
    "sweden": "SE", "switzerland": "CH", "bulgaria": "BG", "romania": "RO",
    "israel": "IL", "india": "IN", "singapore": "SG", "australia": "AU",
    "new zealand": "NZ", "japan": "JP", "south korea": "KR", "philippines": "PH",
    "china": "CN", "mexico": "MX", "brazil": "BR", "argentina": "AR",
    "colombia": "CO", "jamaica": "JM",
}

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "hawaii", "idaho", "illinois",
    "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming", "district of columbia",
}

REMOTE_WORDS = ("remote", "teletravail", "work from home", "wfh", "anywhere", "a distance")

# Words dropped from a location part before matching it.
NOISE_WORDS = {
    "headquarters", "hq", "office", "offices", "hybrid", "onsite", "on site",
    "in office", "flexible", "based", "only", "first", "remote", "teletravail",
    "a distance", "work from home", "wfh", "anywhere", "or", "and", "within",
    "the", "in", "of", "site",
}

# Hyphenated names that must not be split on their hyphens.
_HYPHENATED = (
    "colombie-britannique", "nouveau-brunswick", "nouvelle-ecosse",
    "terre-neuve-et-labrador", "ile-du-prince-edouard", "territoires du nord-ouest",
    "niagara-on-the-lake", "trois-rivieres", "saint-catharines", "sault-ste-marie",
)

_MULTI_LOCATIONS = re.compile(r"^\s*\d+\s+(locations?|emplacements?)\s*$", re.I)


# --- helpers ----------------------------------------------------------------

def fold(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("'", "").replace("’", "").replace(".", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def normalize_country(value: str | None) -> str | None:
    """ISO alpha-2 code from a code ("ca", "CAN") or a name ("Canada")."""
    if not value or not value.strip():
        return None
    key = fold(value)
    if key in COUNTRY_NAMES:
        return COUNTRY_NAMES[key]
    if len(key) == 2 and key.isalpha():
        return key.upper()
    if len(key) == 3 and key.isalpha():
        return {"can": "CA", "usa": "US", "gbr": "GB", "ind": "IN"}.get(key)
    return None


def normalize_province(value: str | None) -> str | None:
    """Canadian province code from a code ("on") or a name ("Québec")."""
    if not value or not value.strip():
        return None
    key = fold(value)
    if key.upper() in PROVINCE_CODES and len(key) == 2:
        return key.upper()
    return PROVINCE_NAMES.get(key)


def _is_remote(text: str) -> bool:
    key = f" {fold(text)} "
    return any(f" {w} " in key for w in REMOTE_WORDS)


def _strip_noise(key: str) -> str:
    words = f" {key} "
    for noise in sorted(NOISE_WORDS, key=len, reverse=True):
        words = words.replace(f" {noise} ", " ")
    return " ".join(words.split())


def _known_city(key: str) -> tuple[str | None, str | None, bool]:
    """(city key, province, ambiguous) for a folded city name, or Nones."""
    if key in CITY_ALIASES:
        return key, CITY_ALIASES[key][1], False
    if key in CITIES:
        return key, CITIES[key], False
    if key in AMBIGUOUS_CITIES:
        return key, AMBIGUOUS_CITIES[key], True
    return None, None, False


def _display_city(part: str, key: str) -> str:
    if key in CITY_ALIASES:
        return CITY_ALIASES[key][0]
    if fold(part) != key:
        # Matched after dropping remarks: "Toronto Headquarters" -> "Toronto".
        words = [w for w in part.split() if fold(w) not in NOISE_WORDS]
        part = " ".join(words) or part
    cleaned = " ".join(part.split())
    # Workday shouts ("TORONTO"); make it readable.
    return cleaned.title() if cleaned.isupper() else cleaned


# --- text parsing -------------------------------------------------------------

def _split_places(text: str) -> list[str]:
    """Split a field that lists several places."""
    pieces = re.split(r"\s*[;|\n]\s*|\s+or\s+", text)
    return [p for p in pieces if p.strip()]


def _split_parts(place: str) -> list[str]:
    """Split one place into its parts: city, province, country, remarks."""
    text = unicodedata.normalize("NFC", place)
    # Same length as text, so positions found here apply to the original.
    plain = "".join(unicodedata.normalize("NFKD", c)[0] for c in text).lower()
    chars = list(text)
    for name in _HYPHENATED:
        for match in re.finditer(re.escape(name), plain):
            for i in range(match.start(), match.end()):
                if chars[i] == "-":
                    chars[i] = " "
    parts = re.split(r"\s*[,()/\[\]\u2013\u2014:]\s*|\s+-\s+|-", "".join(chars))
    return [p.strip() for p in parts if p and p.strip()]


def _parse_one(place: str, canadian_company: bool) -> Location:
    raw = place.strip()
    loc = Location(raw=raw, remote=_is_remote(raw))
    if _MULTI_LOCATIONS.match(raw):
        return loc

    city_key: str | None = None
    city_province: str | None = None
    city_ambiguous = False
    unknown: list[str] = []
    codes: list[str] = []  # two-letter uppercase tokens, resolved at the end
    us_state = False

    for part in _split_parts(raw):
        # "Toronto ON" without a comma: peel off a trailing code.
        words = part.split()
        if len(words) > 1 and len(words[-1]) == 2 and words[-1].isupper():
            codes.append(words[-1])
            part = " ".join(words[:-1])

        if len(part) == 2 and part.isupper() and fold(part) not in CITY_ALIASES:
            codes.append(part)
            continue

        key = fold(part)
        if not key:
            continue
        matched = False
        for candidate in dict.fromkeys((key, _strip_noise(key))):
            if not candidate:
                continue
            if candidate in COUNTRY_NAMES:
                loc.country = loc.country or COUNTRY_NAMES[candidate]
            elif candidate in PROVINCE_NAMES:
                loc.province = loc.province or PROVINCE_NAMES[candidate]
            elif (found := _known_city(candidate))[0]:
                if city_key is None:
                    city_key, city_province, city_ambiguous = found
                    loc.city = _display_city(part, candidate)
            elif candidate in US_STATE_NAMES:
                us_state = True
            else:
                continue
            matched = True
            break
        if not matched and _strip_noise(key):
            unknown.append(part)

    foreign_city = any(fold(u) in FOREIGN_CITIES for u in unknown)

    # Two-letter codes: Canadian province, US state, or "CA" (California vs Canada).
    for code in codes:
        if code == "CA":
            if city_key and not foreign_city:
                loc.country = loc.country or "CA"
            elif unknown or us_state:
                us_state = True
            else:
                loc.country = loc.country or "CA"
        elif code in PROVINCE_CODES and not foreign_city:
            loc.province = loc.province or code
        elif code in US_STATE_CODES:
            us_state = True
        elif code in ("US", "UK"):
            loc.country = loc.country or ("US" if code == "US" else "GB")

    if loc.city is None and unknown:
        first = unknown[0]
        loc.city = first.title() if first.isupper() else " ".join(first.split())

    if us_state and loc.country is None and loc.province is None:
        loc.country = "US"

    _resolve_canada(loc, city_province, city_ambiguous, canadian_company)
    return loc


def _resolve_canada(
    loc: Location, city_province: str | None, city_ambiguous: bool, canadian_company: bool
) -> None:
    """Fill country and province from what is known."""
    if loc.province in PROVINCE_CODES:
        loc.country = loc.country or "CA"
        if loc.country != "CA":
            loc.province = None
    if city_province and loc.province is None:
        if loc.country == "CA":
            # "London, Canada" or "Toronto, Canada".
            loc.province = city_province
        elif loc.country is None and (not city_ambiguous or canadian_company):
            loc.country = "CA"
            loc.province = city_province


def parse_text(text: str | None, *, canadian_company: bool = False, remote: bool = False) -> list[Location]:
    """Parse a location string into one Location per place it names."""
    if not text or not text.strip():
        return [Location(remote=remote)] if remote else []
    locations = [_parse_one(place, canadian_company) for place in _split_places(text)]
    if remote:
        for loc in locations:
            loc.remote = True
    return locations


# --- structured fields -----------------------------------------------------------

def from_parts(
    city: str | None = None,
    region: str | None = None,
    country: str | None = None,
    *,
    remote: bool = False,
    raw: str = "",
    canadian_company: bool = False,
) -> Location:
    """Build a Location from separate city / region / country fields.

    Falls back to parsing *raw* (or the joined parts) when the fields don't say
    enough on their own.
    """
    city = (city or "").strip() or None
    region = (region or "").strip() or None
    country_code = normalize_country(country)
    raw = raw.strip() or ", ".join(p for p in (city, region, (country or "").strip() or None) if p)

    province = None
    if country_code in ("CA", None):
        province = normalize_province(region)
        if province:
            country_code = "CA"

    if country_code is None and province is None and raw:
        # Not enough structure: let the text parser try.
        parsed = parse_text(raw, canadian_company=canadian_company)
        loc = parsed[0] if parsed else Location(raw=raw)
        loc.remote = loc.remote or remote
        if city and not loc.city:
            loc.city = city
        return loc

    loc = Location(
        city=city,
        province=province if country_code == "CA" else region,
        country=country_code,
        remote=remote or _is_remote(raw),
        raw=raw,
    )
    if loc.city and country_code in ("CA", None):
        key = fold(loc.city)
        _, city_province, ambiguous = _known_city(key)
        _resolve_canada(loc, city_province, ambiguous, canadian_company)
    return loc


def is_canadian(locations: Iterable[Location], canadian_company: bool) -> bool:
    """Should a job with these locations be stored?

    Yes when any location is in Canada, or the job is remote with no country
    and the company is Canadian.
    """
    locations = list(locations)
    if any(loc.in_canada for loc in locations):
        return True
    return canadian_company and any(loc.remote and loc.country is None for loc in locations)
