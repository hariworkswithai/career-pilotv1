"""Deterministic deduplication fingerprinting."""

from __future__ import annotations

import hashlib
import re

from app.schemas.opportunities import NormalizedOpportunity, RawJob

_WS = re.compile(r"\s+")


def _slug(value: str) -> str:
    return _WS.sub(" ", (value or "").lower()).strip()


def fingerprint(raw: RawJob, normalized: NormalizedOpportunity) -> str:
    """Stable key: provider + normalized title + company + city (when present)."""
    city = _slug(normalized.location.city or "")
    parts = [normalized.provider, _slug(normalized.title), _slug(normalized.company_name), city]
    base = "|".join(parts)
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()
    return f"{normalized.provider}:{digest}"
