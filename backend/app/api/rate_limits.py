"""Per-client rate-limit FastAPI dependencies backed by the in-process limiter.

Routes declare e.g. ``dependencies=[Depends(rate_limit_ai)]``. For
multi-instance deployments replace the module-level limiters with a shared
store (e.g. Redis); the dependency interface stays the same.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.security.rate_limit import RateLimiter

_ai_limiter = RateLimiter(max_requests=30, window_seconds=60)
_default_limiter = RateLimiter(max_requests=120, window_seconds=60)
_admin_limiter = RateLimiter(max_requests=30, window_seconds=60)
_sensitive_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _check(limiter: RateLimiter, key: str) -> None:
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again shortly.",
        )


def _client_key(request: Request, scope: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{scope}:{host}"


async def rate_limit_default(request: Request) -> None:
    """General browsing: 120 req/min per client."""
    _check(_default_limiter, _client_key(request, "default"))


async def rate_limit_ai(request: Request) -> None:
    """AI endpoints (parse/analyze/enhance/explain): 30 req/min per client."""
    _check(_ai_limiter, _client_key(request, "ai"))


async def rate_limit_admin(request: Request) -> None:
    """Admin mutations, source testing and manual ingestion: 30 req/min."""
    _check(_admin_limiter, _client_key(request, "admin"))


async def rate_limit_sensitive(request: Request) -> None:
    """Uploads, data export and account deletion: 10 req/min per client."""
    _check(_sensitive_limiter, _client_key(request, "sensitive"))


def reset_limiters() -> None:
    """Test helper: clear all in-process rate-limit state."""
    for limiter in (_ai_limiter, _default_limiter, _admin_limiter, _sensitive_limiter):
        limiter._hits.clear()
