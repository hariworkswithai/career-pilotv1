"""Repository protocol and shared query helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.schemas.common import ApplicationStatus
from app.schemas.operations import (
    AiUsageLog,
    Application,
    AuditLog,
    JobSource,
    Notification,
)
from app.schemas.opportunities import NormalizedOpportunity, OpportunityFilters, OpportunityRecord
from app.schemas.profiles import (
    ApplicationAnswerProfile,
    ApplicationPreferences,
    JobPreferences,
    NotificationPreferences,
    Profile,
)
from app.schemas.resumes import ResumeBase, ResumeVersion


class Repository(Protocol):
    """Storage contract used by all service/routers layers."""

    # Access control ----------------------------------------------------
    def is_admin(self, user_id: str) -> bool: ...

    def set_admin(self, user_id: str, is_admin: bool = True) -> None:
        """Grant/revoke admin role (dev + tests; production uses the admins table)."""

    # Opportunities -----------------------------------------------------
    def upsert_opportunity(self, opp: NormalizedOpportunity, fingerprint: str, source_id: str | None = None) -> tuple[str, bool]:
        """Insert or update by dedup fingerprint. Returns (id, created)."""

    def get_opportunity(self, opportunity_id: str) -> OpportunityRecord | None: ...

    def list_opportunities(
        self,
        filters: OpportunityFilters,
        page: int,
        page_size: int,
        internships_only: bool = False,
    ) -> tuple[list[OpportunityRecord], int]: ...

    def count_by_source_key(self) -> dict[str, int]:
        """Admin helper: stored-opportunity counts keyed by source_key."""

    def mark_stale_before(self, provider: str, cutoff: datetime) -> int: ...

    def mark_expired_before(self, cutoff: datetime) -> int:
        """Retire stale listings missing longer than the cutoff (14 days)."""

    def list_cities(self) -> list[str]:
        """Distinct normalized city names present in the catalog."""

    # Job sources -----------------------------------------------------
    def list_sources(self) -> list[JobSource]: ...

    def get_source(self, source_id: str) -> JobSource | None: ...

    def upsert_source(self, source: JobSource) -> str:
        """Insert or update by (source_type, board_identifier). Returns id."""

    def set_source_active(self, source_id: str, active: bool) -> bool: ...

    def record_source_sync(
        self, source_id: str, *, success: bool, error: str = ""
    ) -> None:
        """Update last-synced timestamp, health status and last error."""

    # Saved -------------------------------------------------------------
    def list_saved(self, user_id: str) -> list[str]: ...

    def add_saved(self, user_id: str, opportunity_id: str) -> None: ...

    def remove_saved(self, user_id: str, opportunity_id: str) -> None: ...

    # Profile & preferences --------------------------------------------
    def get_profile(self, user_id: str) -> Profile | None: ...

    def list_profiles(self, limit: int = 100) -> list[Profile]:
        """Admin overview helper: most recently stored profiles first."""

    def upsert_profile(self, profile: Profile) -> None: ...

    def get_job_preferences(self, user_id: str) -> JobPreferences | None: ...

    def upsert_job_preferences(self, prefs: JobPreferences) -> None: ...

    def get_application_preferences(self, user_id: str) -> ApplicationPreferences | None: ...

    def upsert_application_preferences(self, prefs: ApplicationPreferences) -> None: ...

    def get_notification_preferences(self, user_id: str) -> NotificationPreferences | None: ...

    def upsert_notification_preferences(self, prefs: NotificationPreferences) -> None: ...

    def get_answer_profile(self, user_id: str) -> ApplicationAnswerProfile | None: ...

    def upsert_answer_profile(self, profile: ApplicationAnswerProfile) -> None: ...

    # Resumes -----------------------------------------------------------
    def insert_resume(self, resume: ResumeBase) -> str: ...

    def get_resume(self, resume_id: str) -> ResumeBase | None: ...

    def list_resumes(self, user_id: str) -> list[ResumeBase]: ...

    def delete_resume(self, resume_id: str, user_id: str) -> bool: ...

    def save_resume_parsed(self, resume_id: str, parsed: dict) -> None:
        """Store AI-parsed structured data for a resume (derived, never the original)."""

    def insert_resume_version(self, version: ResumeVersion) -> str: ...

    def get_resume_version(self, version_id: str) -> ResumeVersion | None: ...

    def list_resume_versions(self, parent_resume_id: str) -> list[ResumeVersion]:
        """Active (non-archived) versions, ascending by version number."""

    def archive_resume_version(self, version_id: str, user_id: str) -> bool:
        """Soft-delete a version it is not required for application history."""

    def application_uses_resume_version(self, version_id: str) -> bool: ...

    # Applications ------------------------------------------------------
    def insert_application(self, app: Application) -> str: ...

    def get_application(self, application_id: str) -> Application | None: ...

    def list_applications(self, user_id: str, status: ApplicationStatus | None = None) -> list[Application]: ...

    def list_all_applications(
        self, status: ApplicationStatus | None = None, limit: int = 100
    ) -> list[Application]:
        """Admin overview helper across all users (snapshots only)."""

    def update_application(self, app: Application) -> None: ...

    def delete_application(self, application_id: str, user_id: str) -> bool: ...

    # Notifications -----------------------------------------------------
    def insert_notification(self, notification: Notification) -> str: ...

    def list_notifications(self, user_id: str) -> list[Notification]: ...

    def mark_notification_read(self, notification_id: str, user_id: str) -> bool: ...

    def mark_all_notifications_read(self, user_id: str) -> None: ...

    # Audit -----------------------------------------------------------
    def insert_audit_log(self, log: AuditLog) -> str: ...

    def list_audit_logs(self, limit: int = 100) -> list[AuditLog]:
        """Newest first. Admin-only at the route layer."""

    # AI usage ----------------------------------------------------------
    def insert_ai_usage(self, log: AiUsageLog) -> str: ...

    def count_ai_usage(self, user_id: str, feature: str, since: datetime) -> int: ...

    def list_ai_usage(self, user_id: str | None = None) -> list[AiUsageLog]: ...

    # Account lifecycle -------------------------------------------------
    def delete_user_data(self, user_id: str) -> None:
        """Remove every user-owned row (profiles, resumes, applications, …)."""
