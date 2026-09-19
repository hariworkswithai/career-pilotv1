"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_repository
from app.core.config import get_settings
from app.db.base import Repository
from app.schemas.operations import HealthResult

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResult, include_in_schema=False)
async def health(repository: Repository = Depends(get_repository)) -> HealthResult:
    settings = get_settings()
    checks: dict[str, bool | str] = {"repository": True}
    ping = getattr(repository, "ping", None)
    if callable(ping):
        checks["repository"] = bool(ping())
        checks["storage_backend"] = "postgres"
    else:
        checks["storage_backend"] = settings.repository_backend
    return HealthResult(
        status="ok" if all(checks.values()) else "degraded",
        environment=settings.environment,
        checks=checks,
        llm_configured=bool(settings.ai_api_key),
        mail_configured=bool(settings.resend_api_key),
    )
