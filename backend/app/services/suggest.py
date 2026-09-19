"""City autocomplete over normalized India cities plus catalog cities.

Deterministic and dependency-free: prefix matches rank before substring
matches, and common spelling variations resolve to one canonical name
(Bangalore/Bengaluru, Bombay/Mumbai, Calcutta/Kolkata, ...). Unrelated
cities are never merged — unknown input only matches by literal text.
"""

from __future__ import annotations

from app.schemas.opportunities import SuggestionItem
from app.services.locations import INDIA_CITIES

# Variant spelling -> canonical city slug. Curated; do not guess beyond it.
CITY_CANONICAL = {
    "bangalore": "bengaluru",
    "bengalooru": "bengaluru",
    "bombay": "mumbai",
    "calcutta": "kolkata",
    "gurgaon": "gurugram",
    "trivandrum": "thiruvananthapuram",
    "cochin": "kochi",
    "pondicherry": "puducherry",
    "alleppey": "alappuzha",
    "calicut": "kozhikode",
    "cawnpore": "kanpur",
    "poona": "pune",
    "mysuru": "mysore",
    "mangaluru": "mangalore",
    "jullundur": "jalandhar",
    "vizag": "visakhapatnam",
    "baroda": "vadodara",
    "secundrabad": "secunderabad",
}

_POPULAR_FIRST = [
    "bengaluru",
    "mumbai",
    "delhi",
    "hyderabad",
    "chennai",
    "pune",
    "kolkata",
    "ahmedabad",
    "gurugram",
    "noida",
]


def canonical_city(name: str) -> str:
    slug = " ".join((name or "").strip().lower().split())
    return CITY_CANONICAL.get(slug, slug)


def display_city(canonical: str) -> str:
    return " ".join(part.capitalize() for part in canonical.split())


def suggest_cities(query: str, catalog_cities: list[str], limit: int = 8) -> list[SuggestionItem]:
    q = " ".join(query.strip().lower().split())
    if not q:
        return []
    q = CITY_CANONICAL.get(q, q)

    known = {canonical_city(c) for c in INDIA_CITIES}
    catalog = {canonical_city(c) for c in catalog_cities if (c or "").strip()}
    candidates = sorted(known | catalog)

    # Alias-prefix matches: "bang" (Bangalore) must find "bengaluru".
    via_alias = {canon for alias, canon in CITY_CANONICAL.items() if alias.startswith(q)}
    starts = [c for c in candidates if c.startswith(q) or c in via_alias]
    contains = [c for c in candidates if q in c and c not in starts]

    def rank(names: list[str]) -> list[str]:
        return sorted(names, key=lambda n: (_POPULAR_FIRST.index(n) if n in _POPULAR_FIRST else 99, n))

    ordered = rank(starts) + rank(contains)
    return [
        SuggestionItem(
            type="city",
            value=name,
            label=display_city(name),
            category="india" if name in known else "catalog",
        )
        for name in ordered[: max(1, limit)]
    ]
