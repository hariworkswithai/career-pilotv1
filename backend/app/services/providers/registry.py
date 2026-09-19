"""Provider registry and SSRF-safe URL construction.

Admin-configured sources must never let the backend fetch arbitrary URLs: every
outbound ingestion URL is constructed here from an allowlisted provider name and
a strictly validated board identifier. Adapters must build URLs only through
:func:`build_source_url`.
"""

from __future__ import annotations

import re

from app.services.providers.base import BaseProvider

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_TEMPLATES = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{identifier}/jobs",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{identifier}",
    "lever": "https://api.lever.co/v0/postings/{identifier}?mode=json",
}

SUPPORTED_PROVIDERS = tuple(_TEMPLATES)


def validate_identifier(identifier: str) -> str:
    """Return the stripped identifier or raise ValueError (SSRF guard)."""
    cleaned = (identifier or "").strip()
    if not _IDENTIFIER_RE.match(cleaned):
        raise ValueError(
            "Invalid board identifier: use 1-64 letters, digits, '.', '_' or '-'."
        )
    return cleaned


def build_source_url(provider: str, identifier: str) -> str:
    """Construct the public ingestion URL for a supported provider.

    Raises ValueError for unknown providers or malformed identifiers so callers
    can surface a safe user-facing error without ever fetching attacker URLs.
    """
    template = _TEMPLATES.get((provider or "").strip().lower())
    if template is None:
        raise ValueError(f"Unsupported source type: {provider!r}")
    return template.format(identifier=validate_identifier(identifier))


def adapter_for(provider: str, source_keys: list[str]) -> BaseProvider:
    """Instantiate the adapter class for a supported provider name."""
    from app.services.providers.ashby import AshbyAdapter
    from app.services.providers.greenhouse import GreenhouseAdapter
    from app.services.providers.lever import LeverAdapter

    name = (provider or "").strip().lower()
    if name == "greenhouse":
        return GreenhouseAdapter(source_keys)
    if name == "ashby":
        return AshbyAdapter(source_keys)
    if name == "lever":
        return LeverAdapter(source_keys)
    raise ValueError(f"Unsupported source type: {provider!r}")
