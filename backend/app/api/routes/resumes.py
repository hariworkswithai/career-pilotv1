"""Resume upload, parsing, analysis, tailoring and versioning endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.api.deps import get_repository
from app.api.rate_limits import rate_limit_ai, rate_limit_sensitive
from app.core.config import get_settings
from app.core.security import VerifiedUser, current_user
from app.db.base import Repository
from app.schemas.resumes import (
    EnhancementDraft,
    ResumeAnalysis,
    ResumeBase,
    ResumeParseResult,
    ResumeUploadResult,
    ResumeVersion,
    ResumeVersionCreate,
)
from app.services.ai import get_ai_provider
from app.services.ai_usage import (
    FEATURE_ENHANCEMENT,
    FEATURE_TAILORING,
    enforce_quota,
    quota_status,
    record_usage,
)
from app.services.resumes import ParseError, analyze_resume, extract_resume
from app.services.storage import delete_user_file, read_user_file, store_user_file

router = APIRouter(prefix="/resumes", tags=["resumes"])

_ALLOWED_TYPES = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _file_type(filename: str, content_type: str) -> str:
    if content_type in _ALLOWED_TYPES.values():
        for ext, mime in _ALLOWED_TYPES.items():
            if mime == content_type:
                return ext
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    if ext in ("pdf", "docx"):
        return ext
    raise HTTPException(status_code=415, detail="Only PDF or DOCX resumes are supported")


def _verify_magic_bytes(content: bytes, ftype: str) -> None:
    """Reject spoofed uploads: the bytes must match the claimed container.

    PDF must start with ``%PDF-``; DOCX must be a ZIP archive containing the
    OOXML content-types part. stdlib only, no new dependencies.
    """
    if ftype == "pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=422,
                detail="File content does not look like a PDF. Please upload a valid PDF resume.",
            )
        return
    if not content.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status_code=422,
            detail="File content does not look like a DOCX document. Please upload a valid DOCX resume.",
        )
    try:
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
        if "[Content_Types].xml" not in names or not any(n.startswith("word/") for n in names):
            raise ValueError("not an OOXML document")
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="File content does not look like a DOCX document. Please upload a valid DOCX resume.",
        ) from exc


@router.post("", response_model=ResumeUploadResult, dependencies=[Depends(rate_limit_sensitive)])
async def upload_resume(
    file: UploadFile = File(...),
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ResumeUploadResult:
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.resume_max_bytes:
        raise HTTPException(status_code=413, detail=f"Resume exceeds {settings.resume_max_mb} MB")

    ftype = _file_type(file.filename or "", file.content_type or "")
    _verify_magic_bytes(content, ftype)
    try:
        extract_resume(content, ftype)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stored_name = store_user_file(user.user_id, file.filename or f"resume.{ftype}", content)
    resume = ResumeBase(
        id="",
        user_id=user.user_id,
        original_filename=file.filename or f"resume.{ftype}",
        stored_filename=stored_name,
        file_type=ftype,
        file_size=len(content),
        parse_status="parsed",
    )
    resume_id = repository.insert_resume(resume)
    return ResumeUploadResult(
        id=resume_id,
        filename=resume.original_filename,
        stored_filename=stored_name,
        file_type=ftype,
        file_size=len(content),
    )


@router.get("", response_model=list[ResumeBase])
async def list_resumes(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> list[ResumeBase]:
    return repository.list_resumes(user.user_id)


@router.get("/{resume_id}", response_model=ResumeBase)
async def get_resume(
    resume_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ResumeBase:
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.get("/{resume_id}/raw")
async def download_resume_raw(
    resume_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> Response:
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    data = read_user_file(user.user_id, resume.stored_filename)
    if data is None:
        raise HTTPException(status_code=404, detail="File missing")
    mimetype = _ALLOWED_TYPES[resume.file_type]
    return Response(content=data, media_type=mimetype)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    delete_user_file(user.user_id, resume.stored_filename)
    repository.delete_resume(resume_id, user.user_id)
    return {"deleted": True}


@router.post("/{resume_id}/analyze", response_model=ResumeAnalysis, dependencies=[Depends(rate_limit_ai)])
async def analyze_uploaded_resume(
    resume_id: str,
    background: BackgroundTasks,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ResumeAnalysis:
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    data = read_user_file(user.user_id, resume.stored_filename)
    if data is None:
        raise HTTPException(status_code=404, detail="File missing")
    text = extract_resume(data, resume.file_type)

    def run() -> None:
        import anyio

        result = anyio.run(get_ai_provider().analyze_resume, text)
        _ = result

    background.add_task(run)
    return analyze_resume(text)


@router.post("/{resume_id}/parse", response_model=ResumeParseResult, dependencies=[Depends(rate_limit_ai)])
async def parse_resume_file(
    resume_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ResumeParseResult:
    """Parse a resume into the canonical structured schema (Gemini Flash).

    The original file is never modified — the structured result is stored as a derived
    `parsed_data` snapshot on the resume row.
    """
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    data = read_user_file(user.user_id, resume.stored_filename)
    if data is None:
        raise HTTPException(status_code=404, detail="File missing")
    text = extract_resume(data, resume.file_type)
    try:
        parsed = await get_ai_provider().parse_resume(text)
    except Exception as exc:  # noqa: BLE001 — surface a user-safe parsing message
        record_usage(
            repository, user.user_id, feature="parsing", success=False, error=repr(exc)[:300]
        )
        raise HTTPException(status_code=422, detail="We couldn't read this file. Please try a clear PDF or DOCX.") from exc

    record_usage(
        repository, user.user_id, feature="parsing", model=get_settings().ai_parse_model, success=True
    )
    repository.save_resume_parsed(resume_id, parsed.model_dump())
    return parsed


@router.post("/{resume_id}/enhance", response_model=EnhancementDraft, dependencies=[Depends(rate_limit_ai)])
async def enhance_resume(
    resume_id: str,
    target_role: str = Query(default=""),
    target_opportunity_id: str | None = Query(default=None),
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> EnhancementDraft:
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    feature = FEATURE_TAILORING if target_opportunity_id else FEATURE_ENHANCEMENT
    enforce_quota(repository, user.user_id, feature)

    provider = get_ai_provider()
    role = target_role or "the target role"
    version_number = len(repository.list_resume_versions(resume_id)) + 1
    label = (
        f"tailored-{target_role.replace(' ', '-') or 'role'}-v{version_number}"
        if target_opportunity_id
        else f"enhanced-v{version_number}"
    )

    data = read_user_file(user.user_id, resume.stored_filename)
    text = extract_resume(data, resume.file_type) if data else ""

    changed = await provider.improve_section("experience", _section(text, "experience"), role)
    skills = await provider.improve_section("skills", _section(text, "skills"), role)

    model = get_settings().ai_model
    record_usage(
        repository,
        user.user_id,
        feature=feature,
        model=model,
        tokens_input=len(text) // 4,
        tokens_output=sum(len(c.enhanced) for c in (changed, skills)) // 4,
        success=True,
    )
    status_state = quota_status(repository, user.user_id, feature)
    return EnhancementDraft(
        version_label=label,
        target_opportunity_id=target_opportunity_id,
        changes=[changed, skills],
        quota_used=status_state.used,
        quota_limit=status_state.limit,
        quota_remaining=status_state.remaining,
    )


@router.post("/{resume_id}/versions", response_model=ResumeVersion)
async def save_resume_version(
    resume_id: str,
    payload: ResumeVersionCreate,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ResumeVersion:
    """Persist an approved enhancement/tailoring as a new immutable version.

    The user reviews the AI draft first (enhance endpoint) and only post-save for the
    version to exist — the original resume and every earlier version stay untouched.
    """
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    versions = repository.list_resume_versions(resume_id)
    version_number = len(versions) + 1
    label = payload.version_label.strip() or f"version-{version_number}"
    sections = {change.section: change.enhanced for change in payload.changes if change.section}
    version = ResumeVersion(
        id="",
        user_id=user.user_id,
        parent_resume_id=resume_id,
        target_opportunity_id=payload.target_opportunity_id,
        version_label=label,
        version_number=version_number,
        stored_filename=resume.stored_filename,
        file_type=resume.file_type,
        parsed_data={"enhanced_sections": sections},
        enhancement_metadata={
            "target_opportunity_id": payload.target_opportunity_id,
            "accepted_changes": len(payload.changes),
            "source": "review-confirmed",
        },
    )
    version_id = repository.insert_resume_version(version)
    return repository.get_resume_version(version_id) or version


@router.delete("/{resume_id}/versions/{version_id}")
async def delete_resume_version(
    resume_id: str,
    version_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    """Soft-delete a version unless it is required by an application's history."""
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    version = repository.get_resume_version(version_id)
    if not version or version.parent_resume_id != resume_id or version.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Version not found")
    if repository.application_uses_resume_version(version_id):
        raise HTTPException(
            status_code=409,
            detail="This version is used by an application and must be preserved.",
        )
    if not repository.archive_resume_version(version_id, user.user_id):
        raise HTTPException(status_code=409, detail="This version is used by an application and must be preserved.")
    return {"deleted": True, "preserved": False}


@router.get("/{resume_id}/versions", response_model=list[ResumeVersion])
async def list_resume_versions(
    resume_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> list[ResumeVersion]:
    resume = repository.get_resume(resume_id)
    if not resume or resume.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    return repository.list_resume_versions(resume_id)


def _section(text: str, name: str) -> str:
    import re as _re

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    idx: list[int] = []
    for i, line in enumerate(lines):
        if _re.match(rf"^\s*{name}\b\s*$", line, flags=_re.IGNORECASE):
            idx.append(i)
    if not idx:
        return ""
    start = idx[0] + 1
    end = len(lines)
    for other in idx[1:]:
        end = other
        break
    return "\n".join(lines[start:end])[:4000]
