"""Admin endpoints. Every route requires the `require_admin` dependency.

Authorization is enforced server-side (403 for non-admins) and backed by RLS in the
production database; the UI never gates access alone. Destructive and sensitive
actions write server-side audit records.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.api.deps import get_repository
from app.api.rate_limits import rate_limit_admin
from app.core.security import VerifiedUser, require_admin
from app.db.base import Repository
from app.schemas.common import ApplicationStatus
from app.schemas.operations import (
    AdminUserOverview,
    AiUsageLog,
    Application,
    AuditLog,
    JobSource,
    JobSourceCreate,
    JobSourceUpdate,
    RoleChangeRequest,
    SourceTestResult,
    SupportAccessRequest,
    SyncResult,
)
from app.schemas.opportunities import OpportunityFilters
from app.services import audit as audit_log
from app.services.providers.pipeline import run_ingestion
from app.services.providers.registry import (
    SUPPORTED_PROVIDERS,
    adapter_for,
    validate_identifier,
)
from app.services.storage import read_user_file

log = logging.getLogger("careerpilot.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def admin_status(
    repository: Repository = Depends(get_repository),
    _user: VerifiedUser = Depends(require_admin),
) -> dict:
    _, job_total = repository.list_opportunities(OpportunityFilters(), page=1, page_size=1)
    logs = repository.list_ai_usage()
    sources = repository.list_sources()
    return {
        "service": "ok",
        "active_jobs": job_total,
        "ai_usage_events": len(logs),
        "unique_users_touching_ai": len({log.user_id for log in logs}),
        "sources_total": len(sources),
        "sources_active": sum(1 for s in sources if s.is_active),
        "sources_failed": sum(1 for s in sources if s.last_sync_status == "failed"),
    }


@router.get("/ai-usage", response_model=list[AiUsageLog])
async def admin_ai_usage(
    repository: Repository = Depends(get_repository),
    _user: VerifiedUser = Depends(require_admin),
) -> list[AiUsageLog]:
    return repository.list_ai_usage()


@router.get("/users", response_model=list[AdminUserOverview])
async def admin_users(
    limit: int = Query(default=50, ge=1, le=200),
    repository: Repository = Depends(get_repository),
    _user: VerifiedUser = Depends(require_admin),
) -> list[AdminUserOverview]:
    """User overview without private content (no resumes, no application detail)."""
    overviews: list[AdminUserOverview] = []
    for profile in repository.list_profiles(limit):
        overviews.append(
            AdminUserOverview(
                user_id=profile.user_id,
                full_name=profile.full_name,
                is_admin=repository.is_admin(profile.user_id),
                onboarding_completed=profile.onboarding_completed,
                applications=len(repository.list_applications(profile.user_id)),
                resumes=len(repository.list_resumes(profile.user_id)),
                saved_jobs=len(repository.list_saved(profile.user_id)),
            )
        )
    return overviews


@router.post("/users/{user_id}/role", response_model=AdminUserOverview)
async def admin_set_role(
    user_id: str,
    payload: RoleChangeRequest,
    request: Request,
    repository: Repository = Depends(get_repository),
    admin: VerifiedUser = Depends(require_admin),
    _rl: None = Depends(rate_limit_admin),
) -> AdminUserOverview:
    if payload.is_admin is False and user_id == admin.user_id:
        raise HTTPException(status_code=409, detail="Admins cannot revoke their own role")
    repository.set_admin(user_id, payload.is_admin)
    audit_log.log_audit(
        repository,
        actor_user_id=admin.user_id,
        action=audit_log.USER_ROLE_CHANGE,
        resource_type="user",
        resource_id=user_id,
        metadata={"is_admin": payload.is_admin},
        request=request,
    )
    users = await admin_users(limit=200, repository=repository, _user=admin)
    updated = next((u for u in users if u.user_id == user_id), None)
    if updated is None:
        return AdminUserOverview(user_id=user_id, is_admin=payload.is_admin)
    return updated


@router.get("/applications", response_model=list[Application])
async def admin_applications(
    status: ApplicationStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    repository: Repository = Depends(get_repository),
    _user: VerifiedUser = Depends(require_admin),
) -> list[Application]:
    return repository.list_all_applications(status, limit)


@router.get("/audit-logs", response_model=list[AuditLog])
async def admin_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    repository: Repository = Depends(get_repository),
    _user: VerifiedUser = Depends(require_admin),
) -> list[AuditLog]:
    return repository.list_audit_logs(limit)


@router.get("/sources", response_model=list[JobSource])
async def admin_sources(
    repository: Repository = Depends(get_repository),
    _user: VerifiedUser = Depends(require_admin),
) -> list[JobSource]:
    return repository.list_sources()


@router.post("/sources", response_model=JobSource)
async def admin_create_source(
    payload: JobSourceCreate,
    request: Request,
    repository: Repository = Depends(get_repository),
    admin: VerifiedUser = Depends(require_admin),
    _rl: None = Depends(rate_limit_admin),
) -> JobSource:
    source_type = (payload.source_type or "").strip().lower()
    if source_type not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported source type. Choose one of: {', '.join(SUPPORTED_PROVIDERS)}.",
        )
    try:
        identifier = validate_identifier(payload.board_identifier)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    source = JobSource(
        source_type=source_type,
        board_identifier=identifier,
        company_name=payload.company_name.strip(),
    )
    source_id = repository.upsert_source(source)
    audit_log.log_audit(
        repository,
        actor_user_id=admin.user_id,
        action=audit_log.SOURCE_CREATE,
        resource_type="job_source",
        resource_id=source_id,
        metadata={"source_type": source_type, "board_identifier": identifier},
        request=request,
    )
    created = repository.get_source(source_id)
    assert created is not None
    return created


@router.patch("/sources/{source_id}", response_model=JobSource)
async def admin_update_source(
    source_id: str,
    payload: JobSourceUpdate,
    request: Request,
    repository: Repository = Depends(get_repository),
    admin: VerifiedUser = Depends(require_admin),
    _rl: None = Depends(rate_limit_admin),
) -> JobSource:
    source = repository.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    was_active = source.is_active
    if payload.company_name is not None:
        source.company_name = payload.company_name.strip()
    if payload.is_active is not None:
        repository.set_source_active(source_id, payload.is_active)
    else:
        repository.upsert_source(source)
    updated = repository.get_source(source_id)
    assert updated is not None
    if payload.is_active is not None and payload.is_active != was_active:
        action = audit_log.SOURCE_ENABLE if payload.is_active else audit_log.SOURCE_DISABLE
    else:
        action = audit_log.SOURCE_UPDATE
    audit_log.log_audit(
        repository,
        actor_user_id=admin.user_id,
        action=action,
        resource_type="job_source",
        resource_id=source_id,
        metadata={"company_name": updated.company_name, "is_active": updated.is_active},
        request=request,
    )
    return updated


@router.post("/sources/{source_id}/test", response_model=SourceTestResult)
async def admin_test_source(
    source_id: str,
    request: Request,
    repository: Repository = Depends(get_repository),
    admin: VerifiedUser = Depends(require_admin),
    _rl: None = Depends(rate_limit_admin),
) -> SourceTestResult:
    """Probe a source's public endpoint. Safe result; details stay server-side."""
    source = repository.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        adapter = adapter_for(source.source_type, [source.board_identifier])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        jobs = await asyncio.wait_for(adapter.fetch_source(source.board_identifier), timeout=25)
    except (httpx.HTTPError, TimeoutError) as exc:
        log.warning("source test failed for %s: %r", source_id, exc)
        audit_log.log_audit(
            repository, actor_user_id=admin.user_id, action=audit_log.SOURCE_TEST,
            resource_type="job_source", resource_id=source_id,
            metadata={"ok": False}, request=request,
        )
        return SourceTestResult(
            ok=False,
            message="We couldn't connect to this job source. Please check the source details.",
            source_type=source.source_type,
            board_identifier=source.board_identifier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit_log.log_audit(
        repository, actor_user_id=admin.user_id, action=audit_log.SOURCE_TEST,
        resource_type="job_source", resource_id=source_id,
        metadata={"ok": True, "jobs_found": len(jobs)}, request=request,
    )
    return SourceTestResult(
        ok=True,
        message=f"Connected. Found {len(jobs)} published posting(s).",
        jobs_found=len(jobs),
        source_type=source.source_type,
        board_identifier=source.board_identifier,
    )


@router.post("/sources/{source_id}/trigger", response_model=SyncResult)
async def admin_trigger_source(
    source_id: str,
    request: Request,
    repository: Repository = Depends(get_repository),
    admin: VerifiedUser = Depends(require_admin),
    _rl: None = Depends(rate_limit_admin),
) -> SyncResult:
    """Manually ingest a single registered source (rate-limited, audited)."""
    source = repository.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.is_active:
        raise HTTPException(status_code=409, detail="Source is disabled")
    try:
        adapter = adapter_for(source.source_type, [source.board_identifier])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await run_ingestion(repository, [adapter])
    failed = bool(result.errors)
    repository.record_source_sync(
        source_id, success=not failed, error=result.errors[0] if failed else ""
    )
    audit_log.log_audit(
        repository, actor_user_id=admin.user_id, action=audit_log.INGESTION_TRIGGER,
        resource_type="job_source", resource_id=source_id,
        metadata={"fetched": result.fetched, "inserted": result.inserted, "errors": len(result.errors)},
        request=request,
    )
    return result


@router.post("/support/resume-access")
async def admin_support_resume_access(
    payload: SupportAccessRequest,
    request: Request,
    repository: Repository = Depends(get_repository),
    admin: VerifiedUser = Depends(require_admin),
    _rl: None = Depends(rate_limit_admin),
) -> Response:
    """One-time support access to a resume file. Mandatory reason, always audited.

    Normal admin screens never expose resume content; this explicit endpoint is
    the only path, and every call is recorded.
    """
    resume = repository.get_resume(payload.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    audit_log.log_audit(
        repository,
        actor_user_id=admin.user_id,
        action=audit_log.RESUME_SUPPORT_ACCESS,
        resource_type="resume",
        resource_id=payload.resume_id,
        metadata={"reason": payload.reason, "access_type": "support_view"},
        request=request,
    )
    content = read_user_file(resume.user_id, resume.stored_filename)
    if content is None:
        raise HTTPException(status_code=404, detail="Resume file unavailable")
    media = "application/pdf" if resume.file_type == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return Response(content=content, media_type=media)
