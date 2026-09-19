"""Notifications feed endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_repository
from app.core.security import VerifiedUser, current_user
from app.db.base import Repository
from app.schemas.operations import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[Notification])
async def list_notifications(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> list[Notification]:
    return repository.list_notifications(user.user_id)


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    if not repository.mark_notification_read(notification_id, user.user_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"read": True}


@router.post("/read-all")
async def mark_all_read(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    repository.mark_all_notifications_read(user.user_id)
    return {"read": True}
