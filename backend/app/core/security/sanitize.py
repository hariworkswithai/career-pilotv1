"""Allowlist based HTML sanitization for untrusted provider content.

Uses nh3 (ammonia bindings). Only safe structural tags survive; scripts, event
handlers, javascript: URLs, and unsafe styles are removed.
"""

from __future__ import annotations

import nh3

ALLOWED_TAGS = {
    "p",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "a",
    "br",
    "span",
    "code",
    "pre",
    "blockquote",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "target"},
}


def sanitize_html(html: str | None) -> str:
    """Return safe HTML, or empty string for None/blank input."""
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer nofollow",
    )
