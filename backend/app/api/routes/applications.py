"""Applications endpoints with status-transition enforcement."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_repository
from app.core.security import VerifiedUser, current_user
from app.db.base import Repository
from app.schemas.common import ApplicationStatus, NotificationType
from app.schemas.operations import Application, ApplicationCreate, ApplicationUpdate
from app.services.applications import can_transition
from app.services.notifications import notify

router = APIRouter(prefix="/applications", tags=["applications"])


def _owned(repository: Repository, application_id: str, user_id: str) -> Application:
    record = repository.get_application(application_id)
    if not record or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="Application not found")
    return record


def _owned_resume_version(repository: Repository, version_id: str | None, user_id: str) -> None:
    """Reject dangling or foreign resume version links (IDOR guard)."""
    if not version_id:
        return
    version = repository.get_resume_version(version_id)
    if not version or version.user_id != user_id:
        raise HTTPException(status_code=404, detail="Resume version not found")


@router.get("", response_model=list[Application])
async def list_applications(
    status: ApplicationStatus | None = None,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> list[Application]:
    return repository.list_applications(user.user_id, status)


@router.post("", response_model=Application)
async def create_application(
    payload: ApplicationCreate,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> Application:
    opp = repository.get_opportunity(payload.opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp.india_eligible.value == "not_eligible":
        raise HTTPException(status_code=422, detail="This role is not eligible for candidates in India")
    _owned_resume_version(repository, payload.resume_version_id, user.user_id)
    application = Application(
        id="",
        user_id=user.user_id,
        opportunity_id=payload.opportunity_id,
        company_snapshot={"name": opp.company_name},
        role_snapshot={"title": opp.title, "location": opp.location.raw},
        status=payload.status,
        resume_version_id=payload.resume_version_id,
        destination=payload.destination,
        destination_url=payload.destination_url,
        notes=payload.notes,
    )
    application_id = repository.insert_application(application)
    notify(
        repository,
        user_id=user.user_id,
        type=NotificationType.APPLICATION_UPDATE,
        title=f"Application started: {opp.title} at {opp.company_name}",
        body="Opening the employer's page does not submit anything yet — confirm here once applied.",
        email=user.email or None,
        email_subject="Application started",
    )
    return repository.get_application(application_id)  # type: ignore[return-value]


@router.get("/{application_id}", response_model=Application)
async def get_application(
    application_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> Application:
    return _owned(repository, application_id, user.user_id)


@router.patch("/{application_id}", response_model=Application)
async def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> Application:
    application = _owned(repository, application_id, user.user_id)
    if payload.resume_version_id is not None:
        _owned_resume_version(repository, payload.resume_version_id, user.user_id)
    if payload.status is not None and payload.status != application.status:
        if not can_transition(application.status, payload.status):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot move application from {application.status.value} to {payload.status.value}",
            )
        if payload.status == ApplicationStatus.APPLIED:
            application.applied_at = datetime.utcnow()
            notify(
                repository,
                user_id=user.user_id,
                type=NotificationType.APPLICATION_UPDATE,
                title="Application submitted",
                body="Marked as applied. Good luck — update the status as you hear back.",
                email=user.email or None,
                email_subject="Application submitted",
            )
    updated = application.model_copy(update=payload.model_dump(exclude_none=True))
    repository.update_application(updated)
    return repository.get_application(application_id)  # type: ignore[return-value]


@router.delete("/{application_id}")
async def delete_application(
    application_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    if not repository.delete_application(application_id, user.user_id):
        raise HTTPException(status_code=404, detail="Application not found")
    return {"deleted": True}
