"""India-first location parsing and eligibility.

Rules (conservative by design):
- Eligible: city/state in India, or remote within India.
- Not eligible: explicit non-India country or US/CA/UK/EU city.
- Ambiguous: worldwide-remote, or location we cannot confidently classify.
"""

from __future__ import annotations

import re

from app.schemas.common import Eligibility, RemoteScope, WorkplaceType
from app.schemas.opportunities import NormalizedLocation

REMOTE_KEYWORDS = ["remote", "wfh", "work from home", "work-from-home", "virtual", "telecommute"]

HYBRID_KEYWORDS = ["hybrid", "mix", "2-3 days", "2 to 3 days"]

INDIA_CITIES = {
    "bengaluru",
    "bangalore",
    "mumbai",
    "pune",
    "delhi",
    "new delhi",
    "gurugram",
    "gurgaon",
    "noida",
    "ghaziabad",
    "faridabad",
    "hyderabad",
    "secunderabad",
    "chennai",
    "kolkata",
    "ahmedabad",
    "surat",
    "jaipur",
    "lucknow",
    "kanpur",
    "nagpur",
    "indore",
    "bhopal",
    "visakhapatnam",
    "vadodara",
    "kochi",
    "kerala",
    "chandigarh",
    "coimbatore",
    "mangalore",
    "mysore",
    "kozhikode",
    "thiruvananthapuram",
    "guwahati",
    "patna",
    "ranchi",
    "bhubaneswar",
    "dehradun",
    "amritsar",
    "ludhiana",
    "vijayawada",
    "tirupati",
    "trivandrum",
    "gandhinagar",
    "nashik",
    "aurangabad",
    "raipur",
    "jodhpur",
    "varanasi",
    "agra",
    "meerut",
    "hubli",
    "madurai",
    "salem",
    "erode",
    "vellore",
    "tiruchirappalli",
    "thanjavur",
    "kannur",
    "alappuzha",
    "kollam",
    "siliguri",
    "durgapur",
    "asansol",
    "jalandhar",
    "belgaum",
    "dharwad",
    "gulbarga",
    "shimla",
    "uddhamsingh nagar",
    "rudrapur",
    "jamshedpur",
    "bokaro",
    "dhanbad",
    "srinagar",
    "jammu",
    "leh",
    "panaji",
    "margao",
    "pondicherry",
    "puducherry",
    "kota",
    "ujjain",
    "gwalior",
    "jabalpur",
}

INDIA_STATES = {
    "andhra pradesh",
    "arunachal pradesh",
    "assam",
    "bihar",
    "chhattisgarh",
    "goa",
    "gujarat",
    "haryana",
    "himachal pradesh",
    "jharkhand",
    "karnataka",
    "kerala",
    "madhya pradesh",
    "maharashtra",
    "manipur",
    "meghalaya",
    "mizoram",
    "nagaland",
    "odisha",
    "orissa",
    "punjab",
    "rajasthan",
    "sikkim",
    "tamil nadu",
    "telangana",
    "tripura",
    "uttar pradesh",
    "uttarakhand",
    "west bengal",
    "delhi",
    "delhi ncr",
    "ncr",
    "chandigarh",
    "puducherry",
    "dadra & nagar haveli",
    "jammu & kashmir",
    "ladakh",
}

NON_INDIA_COUNTRIES = {
    "usa",
    "united states",
    "us",
    "canada",
    "uk",
    "united kingdom",
    "england",
    "australia",
    "germany",
    "france",
    "netherlands",
    "singapore",
    "uae",
    "dubai",
    "qatar",
    "saudi arabia",
    "japan",
    "china",
    "brazil",
    "spain",
    "italy",
    "poland",
    "ireland",
    "switzerland",
    "sweden",
    "norway",
    "denmark",
    "finland",
    "portugal",
    "malaysia",
    "indonesia",
    "vietnam",
    "thailand",
    "philippines",
    "south korea",
}

NON_INDIA_CITIES = {
    "new york",
    "san francisco",
    "seattle",
    "austin",
    "boston",
    "chicago",
    "los angeles",
    "london",
    "manchester",
    "birmingham",
    "toronto",
    "vancouver",
    "sydney",
    "melbourne",
    "berlin",
    "munich",
    "amsterdam",
    "paris",
    "dublin",
    "singapore",
    "zurich",
}

COUNTRY_INDIA = "india"

_SLUG_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")


def _slug(text: str) -> str:
    return _WS_RE.sub(" ", _SLUG_RE.sub(" ", text.lower())).strip()


def parse_workplace(raw: str, is_remote: bool | None = None) -> tuple[WorkplaceType, RemoteScope]:
    """Return (workplace_type, remote_scope) from provider text."""
    text = _slug(raw)
    low = text.lower()
    if is_remote is True or any(k in low for k in REMOTE_KEYWORDS) or "100% remote" in low:
        if "india" in low:
            return WorkplaceType.REMOTE, RemoteScope.INDIA
        if any(k in low for k in ("usa", "united states", "us")) or "u.s." in low:
            return WorkplaceType.REMOTE, RemoteScope.US
        if any(k in low for k in ("canada", "ca")):
            return WorkplaceType.REMOTE, RemoteScope.CANADA
        if any(k in low for k in ("uk", "united kingdom", "england")):
            return WorkplaceType.REMOTE, RemoteScope.UK
        if any(k in low for k in NON_INDIA_COUNTRIES | NON_INDIA_CITIES):
            return WorkplaceType.REMOTE, RemoteScope.OTHER
        return WorkplaceType.REMOTE, RemoteScope.WORLDWIDE
    if any(k in low for k in HYBRID_KEYWORDS):
        return WorkplaceType.HYBRID, RemoteScope.NONE
    if any(k in low for k in INDIA_CITIES) or "india" in low or any(k in low for k in INDIA_STATES):
        return WorkplaceType.ON_SITE, RemoteScope.NONE
    return WorkplaceType.ON_SITE, RemoteScope.NONE


def _find_city(raw: str) -> str | None:
    for token in _slug(raw).split():
        if token in INDIA_CITIES:
            return token
    for city in INDIA_CITIES:
        if _slug(city) in _slug(raw):
            return city
    return None


def _find_state(raw: str) -> str | None:
    for state in INDIA_STATES:
        if _slug(state) in _slug(raw):
            return state
    return None


def location_from_text(raw: str, is_remote: bool | None = None) -> NormalizedLocation:
    """Parse free-text location into a structured India-first location."""
    text = raw or ""
    workplace, scope = parse_workplace(text, is_remote)

    city = _find_city(text)
    state = _find_state(text)
    country = None
    low = text.lower()
    if city or state or ("india" in low):
        country = COUNTRY_INDIA

    return NormalizedLocation(
        raw=text,
        city=city,
        state=state,
        country=country,
        workplace_type=workplace,
        remote_scope=scope,
    )


def determine_eligibility(location: NormalizedLocation, description_text: str = "") -> tuple[Eligibility, str]:
    """Classify India eligibility. Conservation trumps recall."""
    if not location.raw:
        return Eligibility.AMBIGUOUS, "No location provided"

    if location.country == COUNTRY_INDIA or location.city or location.state:
        return Eligibility.ELIGIBLE, "India-based role"

    if location.workplace_type == WorkplaceType.REMOTE:
        if location.remote_scope == RemoteScope.INDIA:
            return Eligibility.ELIGIBLE, "Remote position open to India"
        if location.remote_scope in (RemoteScope.US, RemoteScope.CANADA, RemoteScope.UK, RemoteScope.OTHER):
            return Eligibility.NOT_ELIGIBLE, "Remote role restricted to non-India regions"

    low = f"{location.raw} {description_text}".lower()
    for bad in NON_INDIA_COUNTRIES | NON_INDIA_CITIES:
        if bad in low:
            return Eligibility.NOT_ELIGIBLE, f"Role tied to {bad}"

    if location.workplace_type == WorkplaceType.REMOTE:
        return Eligibility.AMBIGUOUS, "Remote role with unspecified geography"

    return Eligibility.AMBIGUOUS, "Location could not be confidently classified"
