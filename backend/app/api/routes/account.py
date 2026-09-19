"""Account data export and deletion endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_repository
from app.api.rate_limits import rate_limit_sensitive
from app.core.security import VerifiedUser, current_user
from app.db.base import Repository
from app.services import audit as audit_log
from app.services.storage import delete_user_file

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export", dependencies=[Depends(rate_limit_sensitive)])
async def export_data(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    """Data export: profile, preferences, resumes (+versions) and application history."""
    profile = repository.get_profile(user.user_id)
    prefs = repository.get_job_preferences(user.user_id)
    resumes = repository.list_resumes(user.user_id)
    versions = {resume.id: repository.list_resume_versions(resume.id) for resume in resumes}
    applications = repository.list_applications(user.user_id)
    notifications = repository.list_notifications(user.user_id)
    return {
        "profile": profile.model_dump() if profile else None,
        "job_preferences": prefs.model_dump() if prefs else None,
        "resumes": [resume.model_dump() for resume in resumes],
        "resume_versions": {k: [v.model_dump() for v in vs] for k, vs in versions.items()},
        "applications": [app.model_dump() for app in applications],
        "notifications": [n.model_dump() for n in notifications],
        "exported_at": str(datetime.utcnow()),
    }


@router.delete("", dependencies=[Depends(rate_limit_sensitive)])
async def delete_account(
    request: Request,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    """Account deletion: remove every user-owned row and private resume file.

    The Supabase Auth user row itself is removed by the caller via an admin request;
    this endpoint clears application data and stored files server-side.
    """
    for resume in repository.list_resumes(user.user_id):
        delete_user_file(user.user_id, resume.stored_filename)
    repository.delete_user_data(user.user_id)
    audit_log.log_audit(
        repository,
        actor_user_id=user.user_id,
        action=audit_log.ACCOUNT_DELETE,
        resource_type="user",
        resource_id=user.user_id,
        request=request,
    )
    return {"deleted": True}
