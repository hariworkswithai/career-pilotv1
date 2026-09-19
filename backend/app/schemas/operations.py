"""Application, notification, and internal-sync schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApplicationStatus, ApplyDestination


class Application(BaseModel):
    id: str
    user_id: str
    opportunity_id: str
    company_snapshot: dict = Field(default_factory=dict)
    role_snapshot: dict = Field(default_factory=dict)
    status: ApplicationStatus = ApplicationStatus.SAVED
    applied_at: datetime | None = None
    resume_version_id: str | None = None
    destination: ApplyDestination = ApplyDestination.CONTINUE
    destination_url: str = ""
    notes: str = ""
    answer_summary: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApplicationCreate(BaseModel):
    opportunity_id: str
    resume_version_id: str | None = None
    status: ApplicationStatus = ApplicationStatus.SAVED
    destination: ApplyDestination = ApplyDestination.CONTINUE
    destination_url: str = ""
    notes: str = ""


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    resume_version_id: str | None = None
    notes: str | None = None


class Notification(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    body: str = ""
    read_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AiUsageLog(BaseModel):
    id: str = ""
    user_id: str
    feature: str  # parsing | analysis | enhancement | tailoring
    model: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SyncResult(BaseModel):
    started_at: datetime
    completed_at: datetime
    providers_run: list[str]
    fetched: int
    inserted: int
    updated: int
    rejected: int
    stale_marked: int = 0
    expired_marked: int = 0
    errors: list[str] = Field(default_factory=list)


class JobSource(BaseModel):
    """Registered ATS board polled by scheduled ingestion."""

    id: str = ""
    source_type: str = ""  # greenhouse | ashby | lever
    board_identifier: str = ""
    company_name: str = ""
    is_active: bool = True
    last_synced_at: datetime | None = None
    last_sync_status: str = "never"  # never | healthy | warning | failed | disabled
    last_error: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobSourceCreate(BaseModel):
    source_type: str
    board_identifier: str
    company_name: str = ""


class JobSourceUpdate(BaseModel):
    company_name: str | None = None
    is_active: bool | None = None


class SourceTestResult(BaseModel):
    ok: bool
    message: str
    jobs_found: int = 0
    source_type: str = ""
    board_identifier: str = ""


class AuditLog(BaseModel):
    id: str = ""
    actor_user_id: str
    action: str
    resource_type: str = ""
    resource_id: str = ""
    metadata: dict = Field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AdminUserOverview(BaseModel):
    user_id: str
    full_name: str = ""
    is_admin: bool = False
    onboarding_completed: bool = False
    applications: int = 0
    resumes: int = 0
    saved_jobs: int = 0


class RoleChangeRequest(BaseModel):
    is_admin: bool


class SupportAccessRequest(BaseModel):
    resume_id: str
    reason: str = Field(min_length=10, max_length=500)


class HealthResult(BaseModel):
    status: str = "ok"
    environment: str
    checks: dict = Field(default_factory=dict)
    llm_configured: bool = False
    mail_configured: bool = False
