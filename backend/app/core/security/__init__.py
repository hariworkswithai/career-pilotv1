"""Core security helpers: token verification, sanitization, rate limiting.

Security is a designed-in cross-cutting concern, not an add-on.
"""

from __future__ import annotations

from app.core.security.auth import VerifiedUser, current_user, require_admin, verify_access_token
from app.core.security.internal import require_internal_token
from app.core.security.rate_limit import RateLimiter
from app.core.security.sanitize import sanitize_html

__all__ = [
    "VerifiedUser",
    "current_user",
    "require_admin",
    "verify_access_token",
    "require_internal_token",
    "RateLimiter",
    "sanitize_html",
]
