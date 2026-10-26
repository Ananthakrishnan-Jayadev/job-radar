import json
from pathlib import Path

import pytest

from jobradar.locations import (
    from_parts,
    is_canadian,
    normalize_country,
    normalize_province,
    parse_text,
)
from jobradar.models import Location

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())["response"]


def first(text, **kw):
    return parse_text(text, **kw)[0]


# (text, city, province, country, remote)
TEXT_CASES = [
    # Ontario, the common forms
    ("Toronto, ON", "Toronto", "ON", "CA", False),
    ("Toronto, Ontario", "Toronto", "ON", "CA", False),
    ("Toronto, ON, Canada", "Toronto", "ON", "CA", False),
    ("Toronto, Ontario, Canada", "Toronto", "ON", "CA", False),
    ("Toronto ON", "Toronto", "ON", "CA", False),
    ("Toronto", "Toronto", "ON", "CA", False),
    ("TORONTO-Ontario-Canada", "Toronto", "ON", "CA", False),
    ("Toronto-Ontario", "Toronto", "ON", "CA", False),
    ("Toronto Headquarters", "Toronto", "ON", "CA", False),
    ("Mississauga, Ontario", "Mississauga", "ON", "CA", False),
    ("Richmond Hill, ON", "Richmond Hill", "ON", "CA", False),
    ("St. Catharines, ON", "St. Catharines", "ON", "CA", False),
    ("Ottawa / Hybrid", "Ottawa", "ON", "CA", False),
    ("Kanata, Ontario", "Kanata", "ON", "CA", False),
    ("Niagara-on-the-Lake, Ontario", "Niagara on the Lake", "ON", "CA", False),
    # Regions standing for a city
    ("GTA", "Toronto", "ON", "CA", False),
    ("Greater Toronto Area", "Toronto", "ON", "CA", False),
    ("Kitchener-Waterloo", "Kitchener", "ON", "CA", False),
    ("KW", "Kitchener", "ON", "CA", False),
    # Remote in Canada
    ("Remote (Canada)", None, None, "CA", True),
    ("Remote – Canada", None, None, "CA", True),
    ("Remote - Canada", None, None, "CA", True),
    ("Canada - Remote", None, None, "CA", True),
    ("Canada", None, None, "CA", False),
    ("Remote, Ontario", None, "ON", "CA", True),
    ("Toronto, ON (Remote)", "Toronto", "ON", "CA", True),
    ("Remote", None, None, None, True),
    # Other provinces, English and French
    ("Montréal, QC", "Montréal", "QC", "CA", False),
    ("Montreal, Quebec, Canada", "Montreal", "QC", "CA", False),
    ("Québec", None, "QC", "CA", False),
    ("Gatineau, Québec, Canada", "Gatineau", "QC", "CA", False),
    ("Vancouver, British Columbia", "Vancouver", "BC", "CA", False),
    ("Vancouver, BC", "Vancouver", "BC", "CA", False),
    ("Colombie-Britannique", None, "BC", "CA", False),
    ("Calgary, AB", "Calgary", "AB", "CA", False),
    ("Calgary", "Calgary", "AB", "CA", False),
    ("Halifax, Nova Scotia", "Halifax", "NS", "CA", False),
    ("St. John's, NL", "St. John's", "NL", "CA", False),
    ("Télétravail, Canada", None, None, "CA", True),
    # United States and elsewhere
    ("New York City, NY", "New York City", None, "US", False),
    ("San Francisco, CA", "San Francisco", None, "US", False),
    ("San Francisco, California, United States", "San Francisco", None, "US", False),
    ("Austin, TX, United States", "Austin", None, "US", False),
    ("New York, New York, United States", "New York", None, "US", False),
    ("Washington, DC", "Washington", None, "US", False),
    ("California", None, None, "US", False),
    ("Remote - US", None, None, "US", True),
    ("London, UK", "London", None, "GB", False),
    ("Amsterdam, NL", "Amsterdam", None, None, False),
    ("Hamilton, New Zealand", "Hamilton", None, "NZ", False),
    ("Waterloo, IA", "Waterloo", None, "US", False),
    # Ambiguous cities: not Canadian without a hint
    ("London", "London", None, None, False),
    ("Waterloo", "Waterloo", None, None, False),
    ("London, ON", "London", "ON", "CA", False),
    ("Waterloo, Ontario", "Waterloo", "ON", "CA", False),
    ("Richmond, BC", "Richmond", "BC", "CA", False),
    ("London, Canada", "London", "ON", "CA", False),
]


@pytest.mark.parametrize("text,city,province,country,remote", TEXT_CASES)
def test_parse_text(text, city, province, country, remote):
    loc = first(text)
    assert (loc.city, loc.province, loc.country, loc.remote) == (city, province, country, remote)
    assert loc.raw == text


@pytest.mark.parametrize("city", ["London", "Waterloo", "Hamilton", "Kingston", "Windsor", "Cambridge"])
def test_ambiguous_city_resolves_for_canadian_company(city):
    loc = first(city, canadian_company=True)
    assert (loc.province, loc.country) == ("ON", "CA")
    assert first(city).country is None


def test_ambiguous_city_keeps_explicit_foreign_country():
    assert first("London, UK", canadian_company=True).country == "GB"


def test_several_places_greenhouse_style():
    locs = parse_text("New York City, NY; San Francisco, CA")
    assert [(l.city, l.country) for l in locs] == [("New York City", "US"), ("San Francisco", "US")]


def test_several_places_mixed_countries():
    locs = parse_text("Toronto, ON | Remote - US")
    assert [l.country for l in locs] == ["CA", "US"]


def test_workday_location_count_has_no_place():
    loc = first("2 Locations")
    assert (loc.city, loc.province, loc.country) == (None, None, None)
    assert loc.raw == "2 Locations"


def test_empty_text():
    assert parse_text("") == []
    assert parse_text(None) == []
    assert parse_text("", remote=True) == [Location(remote=True)]


def test_remote_flag_from_caller():
    assert first("Canada", remote=True).remote_canada_wide


@pytest.mark.parametrize(
    "value,code",
    [("Canada", "CA"), ("ca", "CA"), ("CAN", "CA"), ("us", "US"), ("United States", "US"),
     ("USA", "US"), ("Netherlands", "NL"), ("", None), (None, None), ("Atlantis", None)],
)
def test_normalize_country(value, code):
    assert normalize_country(value) == code


@pytest.mark.parametrize(
    "value,code",
    [("Ontario", "ON"), ("on", "ON"), ("Québec", "QC"), ("Quebec", "QC"),
     ("Colombie-Britannique", "BC"), ("Newfoundland and Labrador", "NL"), ("TX", None), (None, None)],
)
def test_normalize_province(value, code):
    assert normalize_province(value) == code


# --- structured fields, using the recorded responses --------------------------------

def test_from_parts_ashby_address():
    job = fixture("ashby_wealthsimple.json")["jobs"][0]
    addr = job["address"]["postalAddress"]
    loc = from_parts(addr["addressLocality"], addr["addressRegion"], addr["addressCountry"],
                     remote=job["isRemote"], raw=job["location"])
    assert (loc.city, loc.province, loc.country, loc.remote) == ("Toronto", "ON", "CA", False)


def test_from_parts_ashby_remote_with_empty_address():
    jobs = fixture("ashby_wealthsimple.json")["jobs"]
    job = next(j for j in jobs if j["location"] == "Remote (Canada)")
    addr = job["address"]["postalAddress"]
    loc = from_parts(addr.get("addressLocality"), addr.get("addressRegion"),
                     addr.get("addressCountry"), remote=job["isRemote"], raw=job["location"])
    assert loc.remote_canada_wide


def test_from_parts_workable():
    job = fixture("workable_borrowell.json")["jobs"][0]
    loc = from_parts(job["city"], job["state"], job["country"], remote=job["telecommuting"])
    assert (loc.city, loc.province, loc.country) == ("Toronto", "ON", "CA")


def test_from_parts_rippling_country_only():
    item = fixture("rippling_nesto.json")["items"][0]
    place = item["locations"][0]
    loc = from_parts(place["city"], place["state"], place["countryCode"],
                     remote=place["workplaceType"] == "REMOTE", raw=place["name"])
    assert loc.remote_canada_wide


def test_from_parts_smartrecruiters_us():
    posting = fixture("smartrecruiters_canva.json")["content"][0]
    place = posting["location"]
    loc = from_parts(place["city"], place["region"], place["country"])
    assert (loc.city, loc.province, loc.country) == ("Austin", "TX", "US")


def test_from_parts_recruitee_europe():
    offer = fixture("recruitee_bunq.json")["offers"][0]
    loc = from_parts(offer["city"], offer.get("state_name"), offer["country"])
    assert loc.country in ("NL", "BG")
    assert not loc.in_canada


def test_from_parts_bamboohr_state_without_country():
    loc = from_parts("San Francisco", "California", None)
    assert loc.country == "US"


def test_from_parts_lever_country_code_with_text():
    job = fixture("lever_wattpad.json")[0]
    loc = from_parts(None, None, job["country"], raw=job["categories"]["location"])
    assert loc.country == "CA"
    assert parse_text(job["categories"]["location"])[0].province == "ON"


def test_from_parts_city_only_unambiguous():
    assert from_parts("Ottawa", None, None).province == "ON"


def test_from_parts_city_only_ambiguous():
    assert from_parts("London", None, None).country is None
    assert from_parts("London", None, None, canadian_company=True).country == "CA"


def test_workday_detail_locations():
    info = fixture("workday_sunlife_detail.json")["jobPostingInfo"]
    places = [info["location"], *info["additionalLocations"]]
    locs = [first(p) for p in places]
    assert [(l.city, l.province) for l in locs] == [("Toronto", "ON"), ("Waterloo", "ON")]


# --- storing rule ----------------------------------------------------------------------

def test_is_canadian():
    toronto = Location("Toronto", "ON", "CA")
    remote_unknown = Location(remote=True)
    nyc = Location("New York", None, "US")
    assert is_canadian([nyc, toronto], canadian_company=False)
    assert not is_canadian([nyc], canadian_company=True)
    assert is_canadian([remote_unknown], canadian_company=True)
    assert not is_canadian([remote_unknown], canadian_company=False)
    assert not is_canadian([], canadian_company=True)


def test_label():
    assert Location("Toronto", "ON", "CA").label() == "Toronto, ON"
    assert Location(None, None, "CA", remote=True).label() == "Remote (Canada)"
    assert Location("Austin", "TX", "US").label() == "Austin, TX, US"
    assert Location(remote=True).label() == "Remote"
    assert Location(raw="2 Locations").label() == "2 Locations"
