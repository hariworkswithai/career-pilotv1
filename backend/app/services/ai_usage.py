"""AI usage logging and monthly free-tier quota enforcement.

Every AI invocation is logged server-side to `ai_usage_logs` (user, feature, model,
tokens, success, timestamp). The free tier allows a fixed number of enhancements and
tailorings per calendar month; parsing and analysis are not quota-limited.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.base import Repository
from app.schemas.operations import AiUsageLog

QUOTA_MSG = "You've reached your limit for this month. Upgrade or try again later."

FEATURE_ENHANCEMENT = "enhancement"
FEATURE_TAILORING = "tailoring"


class QuotaStatus(BaseModel):
    feature: str
    used: int
    limit: int
    remaining: int


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)


def used_this_month(repository: Repository, user_id: str, feature: str) -> int:
    return repository.count_ai_usage(user_id, feature, since=_month_start())


def quota_status(repository: Repository, user_id: str, feature: str) -> QuotaStatus:
    limit = get_settings().ai_quota_enhancements if feature == FEATURE_ENHANCEMENT else get_settings().ai_quota_tailorings
    used = used_this_month(repository, user_id, feature)
    return QuotaStatus(feature=feature, used=used, limit=limit, remaining=max(0, limit - used))


def enforce_quota(repository: Repository, user_id: str, feature: str) -> QuotaStatus:
    status = quota_status(repository, user_id, feature)
    if status.remaining <= 0:
        raise HTTPException(status_code=429, detail=QUOTA_MSG)
    return status


def record_usage(
    repository: Repository,
    user_id: str,
    *,
    feature: str,
    model: str = "",
    tokens_input: int = 0,
    tokens_output: int = 0,
    success: bool = True,
    error: str = "",
) -> None:
    log = AiUsageLog(
        id="",
        user_id=user_id,
        feature=feature,
        model=model,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_usd=0.0,
        success=success,
        error=error,
    )
    repository.insert_ai_usage(log)
