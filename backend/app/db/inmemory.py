"""In-memory repository used for development and tests.

Thread-safe enough for tests and local single-process use. Every method mirrors the
Repository protocol; ownership checks are explicit here so IDOR bugs surface in
tests before touching the production repository.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from uuid import uuid4

from app.db.base import Repository
from app.schemas.common import ApplicationStatus
from app.schemas.operations import AiUsageLog, Application, AuditLog, JobSource, Notification
from app.schemas.opportunities import NormalizedOpportunity, OpportunityFilters, OpportunityRecord
from app.schemas.profiles import (
    ApplicationAnswerProfile,
    ApplicationPreferences,
    JobPreferences,
    NotificationPreferences,
    Profile,
)
from app.schemas.resumes import ResumeBase, ResumeVersion


def _score_text(haystack: str, query: str) -> int:
    """Simple relevance: number of query tokens found in haystack."""
    tokens = [t.strip().lower() for t in query.split() if t.strip()]
    if not tokens:
        return 0
    low = haystack.lower()
    return sum(1 for t in tokens if t in low)


class InMemoryRepository(Repository):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._opportunities: dict[str, OpportunityRecord] = {}
        self._saved: dict[str, set[str]] = {}
        self._profiles: dict[str, Profile] = {}
        self._job_prefs: dict[str, JobPreferences] = {}
        self._app_prefs: dict[str, ApplicationPreferences] = {}
        self._notif_prefs: dict[str, NotificationPreferences] = {}
        self._answer_profiles: dict[str, ApplicationAnswerProfile] = {}
        self._resumes: dict[str, ResumeBase] = {}
        self._resume_text: dict[str, str] = {}
        self._resume_versions: dict[str, ResumeVersion] = {}
        self._applications: dict[str, Application] = {}
        self._notifications: dict[str, Notification] = {}
        self._ai_usage: dict[str, AiUsageLog] = {}
        self._audit_logs: dict[str, AuditLog] = {}
        self._sources: dict[str, JobSource] = {}
        self._admins: set[str] = set()

    # Access control ----------------------------------------------------
    def is_admin(self, user_id: str) -> bool:
        with self._lock:
            return user_id in self._admins

    def set_admin(self, user_id: str, is_admin: bool = True) -> None:
        with self._lock:
            if is_admin:
                self._admins.add(user_id)
            else:
                self._admins.discard(user_id)

    # Opportunities -----------------------------------------------------
    def upsert_opportunity(
        self, opp: NormalizedOpportunity, fingerprint: str, source_id: str | None = None
    ) -> tuple[str, bool]:
        with self._lock:
            for existing in self._opportunities.values():
                if existing.dedup_fingerprint == fingerprint:
                    merged = OpportunityRecord(**{**existing.model_dump(), **opp.model_dump()})
                    merged.id = existing.id
                    merged.dedup_fingerprint = fingerprint
                    merged.source_id = source_id
                    merged.status = "active"
                    merged.updated_at = datetime.utcnow()
                    self._opportunities[merged.id] = merged
                    return merged.id, False
            record = OpportunityRecord(**opp.model_dump(), id=str(uuid4()), dedup_fingerprint=fingerprint, source_id=source_id)
            self._opportunities[record.id] = record
            return record.id, True

    def get_opportunity(self, opportunity_id: str) -> OpportunityRecord | None:
        with self._lock:
            rec = self._opportunities.get(opportunity_id)
            return rec.model_copy(deep=True) if rec else None

    def list_opportunities(
        self,
        filters: OpportunityFilters,
        page: int,
        page_size: int,
        internships_only: bool = False,
    ) -> tuple[list[OpportunityRecord], int]:
        with self._lock:
            rows = [r.model_copy(deep=True) for r in self._opportunities.values() if r.is_active and r.published]
            if internships_only:
                rows = [r for r in rows if r.is_internship]
            else:
                rows = [r for r in rows if not r.is_internship]

            q = filters.q.lower().strip()
            if q:
                scored = [
                    (r, self._score_query(r, q) + (2 if r.is_internship and ("intern" in q) else 0))
                    for r in rows
                ]
                rows = [r for r, s in scored if s > 0]
            else:
                scored = [(r, 0) for r in rows]

            if filters.roles:
                wanted = {x.lower() for x in filters.roles}
                rows = [r for r in rows if any(w in r.normalized_title.lower() for w in wanted)]
            if filters.cities:
                wanted = {x.lower() for x in filters.cities}
                rows = [r for r in rows if (r.location.city or "").lower() in wanted]
            if filters.work_modes:
                rows = [r for r in rows if r.location.workplace_type in filters.work_modes]
            if filters.experience_levels:
                rows = [r for r in rows if r.experience_level in filters.experience_levels]
            if filters.employment_types:
                rows = [r for r in rows if r.employment_type in filters.employment_types]
            if filters.min_salary:
                rows = [r for r in rows if (r.salary_min or 0) >= filters.min_salary]
            if filters.posted_days:
                cutoff = datetime.utcnow() - timedelta(days=filters.posted_days)
                rows = [r for r in rows if (r.posted_at or r.created_at) >= cutoff]

            if filters.sort == "recent":
                rows.sort(key=lambda r: r.posted_at or r.created_at, reverse=True)
            else:
                rows.sort(key=lambda r: (self._score_query(r, q), r.posted_at or r.created_at), reverse=True)

            total = len(rows)
            start = (page - 1) * page_size
            return rows[start : start + page_size], total

    def mark_stale_before(self, provider: str, cutoff: datetime) -> int:
        with self._lock:
            count = 0
            for rec in self._opportunities.values():
                if rec.provider == provider and (rec.updated_at or rec.created_at) < cutoff and rec.status == "active":
                    rec.status = "stale"
                    count += 1
            return count

    def mark_expired_before(self, cutoff: datetime) -> int:
        with self._lock:
            count = 0
            for rec in self._opportunities.values():
                if rec.status == "stale" and (rec.updated_at or rec.created_at) < cutoff:
                    rec.status = "expired"
                    count += 1
            return count

    def count_by_source_key(self) -> dict[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for rec in self._opportunities.values():
                counts[rec.source_key] = counts.get(rec.source_key, 0) + 1
            return counts

    def list_cities(self) -> list[str]:
        with self._lock:
            return sorted({(r.location.city or "").strip().lower() for r in self._opportunities.values() if r.location.city})

    # Job sources -----------------------------------------------------
    def list_sources(self) -> list[JobSource]:
        with self._lock:
            return sorted(
                (s.model_copy(deep=True) for s in self._sources.values()),
                key=lambda s: (s.source_type, s.board_identifier),
            )

    def get_source(self, source_id: str) -> JobSource | None:
        with self._lock:
            s = self._sources.get(source_id)
            return s.model_copy(deep=True) if s else None

    def upsert_source(self, source: JobSource) -> str:
        with self._lock:
            for existing in self._sources.values():
                if (
                    existing.source_type == source.source_type
                    and existing.board_identifier == source.board_identifier
                ):
                    existing.company_name = source.company_name or existing.company_name
                    existing.is_active = source.is_active
                    existing.updated_at = datetime.utcnow()
                    return existing.id
            if not source.id:
                source.id = str(uuid4())
            self._sources[source.id] = source.model_copy(deep=True)
            return source.id

    def set_source_active(self, source_id: str, active: bool) -> bool:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                return False
            s.is_active = active
            s.last_sync_status = "disabled" if not active else ("never" if s.last_synced_at is None else s.last_sync_status)
            s.updated_at = datetime.utcnow()
            return True

    def record_source_sync(self, source_id: str, *, success: bool, error: str = "") -> None:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                return
            s.last_synced_at = datetime.utcnow()
            s.last_sync_status = "healthy" if success else "failed"
            s.last_error = "" if success else error[:500]
            s.updated_at = datetime.utcnow()

    def _score_query(self, rec: OpportunityRecord, q: str) -> int:
        haystack = " ".join(
            [
                rec.normalized_title,
                rec.company_name,
                rec.location.city or "",
                rec.location.state or "",
                rec.location.country or "",
                " ".join(rec.skills),
            ]
        )
        return _score_text(haystack, q)

    # Saved -------------------------------------------------------------
    def list_saved(self, user_id: str) -> list[str]:
        with self._lock:
            return sorted(self._saved.get(user_id, set()))

    def add_saved(self, user_id: str, opportunity_id: str) -> None:
        with self._lock:
            self._saved.setdefault(user_id, set()).add(opportunity_id)

    def remove_saved(self, user_id: str, opportunity_id: str) -> None:
        with self._lock:
            if user_id in self._saved:
                self._saved[user_id].discard(opportunity_id)

    # Profile & preferences --------------------------------------------
    def get_profile(self, user_id: str) -> Profile | None:
        with self._lock:
            p = self._profiles.get(user_id)
            return p.model_copy(deep=True) if p else None

    def list_profiles(self, limit: int = 100) -> list[Profile]:
        with self._lock:
            return [p.model_copy(deep=True) for p in list(self._profiles.values())[:limit]]

    def upsert_profile(self, profile: Profile) -> None:
        with self._lock:
            self._profiles[profile.user_id] = profile.model_copy(deep=True)

    def get_job_preferences(self, user_id: str) -> JobPreferences | None:
        with self._lock:
            p = self._job_prefs.get(user_id)
            return p.model_copy(deep=True) if p else None

    def upsert_job_preferences(self, prefs: JobPreferences) -> None:
        with self._lock:
            self._job_prefs[prefs.user_id] = prefs.model_copy(deep=True)

    def get_application_preferences(self, user_id: str) -> ApplicationPreferences | None:
        with self._lock:
            p = self._app_prefs.get(user_id)
            return p.model_copy(deep=True) if p else None

    def upsert_application_preferences(self, prefs: ApplicationPreferences) -> None:
        with self._lock:
            self._app_prefs[prefs.user_id] = prefs.model_copy(deep=True)

    def get_notification_preferences(self, user_id: str) -> NotificationPreferences | None:
        with self._lock:
            p = self._notif_prefs.get(user_id)
            return p.model_copy(deep=True) if p else None

    def upsert_notification_preferences(self, prefs: NotificationPreferences) -> None:
        with self._lock:
            self._notif_prefs[prefs.user_id] = prefs.model_copy(deep=True)

    def get_answer_profile(self, user_id: str) -> ApplicationAnswerProfile | None:
        with self._lock:
            p = self._answer_profiles.get(user_id)
            return p.model_copy(deep=True) if p else None

    def upsert_answer_profile(self, profile: ApplicationAnswerProfile) -> None:
        with self._lock:
            self._answer_profiles[profile.user_id] = profile.model_copy(deep=True)

    # Resumes -----------------------------------------------------------
    def insert_resume(self, resume: ResumeBase) -> str:
        with self._lock:
            if not resume.id:
                resume.id = str(uuid4())
            self._resumes[resume.id] = resume.model_copy(deep=True)
            return resume.id

    def get_resume(self, resume_id: str) -> ResumeBase | None:
        with self._lock:
            r = self._resumes.get(resume_id)
            return r.model_copy(deep=True) if r else None

    def list_resumes(self, user_id: str) -> list[ResumeBase]:
        with self._lock:
            return sorted(
                (r.model_copy(deep=True) for r in self._resumes.values() if r.user_id == user_id),
                key=lambda r: r.created_at,
                reverse=True,
            )

    def delete_resume(self, resume_id: str, user_id: str) -> bool:
        with self._lock:
            r = self._resumes.get(resume_id)
            if not r or r.user_id != user_id:
                return False
            del self._resumes[resume_id]
            self._resume_text.pop(resume_id, None)
            return True

    def insert_resume_version(self, version: ResumeVersion) -> str:
        with self._lock:
            if not version.id:
                version.id = str(uuid4())
            self._resume_versions[version.id] = version.model_copy(deep=True)
            return version.id

    def get_resume_version(self, version_id: str) -> ResumeVersion | None:
        with self._lock:
            v = self._resume_versions.get(version_id)
            return v.model_copy(deep=True) if v else None

    def list_resume_versions(self, parent_resume_id: str) -> list[ResumeVersion]:
        with self._lock:
            return sorted(
                (
                    v.model_copy(deep=True)
                    for v in self._resume_versions.values()
                    if v.parent_resume_id == parent_resume_id and v.status == "active"
                ),
                key=lambda v: v.version_number,
            )

    def save_resume_parsed(self, resume_id: str, parsed: dict) -> None:
        with self._lock:
            resume = self._resumes.get(resume_id)
            if resume:
                resume.parsed_data = parsed
                resume.parse_status = "parsed"

    def archive_resume_version(self, version_id: str, user_id: str) -> bool:
        with self._lock:
            v = self._resume_versions.get(version_id)
            if not v or v.user_id != user_id:
                return False
            if self.application_uses_resume_version(version_id):
                return False
            v.status = "archived"
            return True

    def application_uses_resume_version(self, version_id: str) -> bool:
        with self._lock:
            return any(a.resume_version_id == version_id for a in self._applications.values())

    # Applications ------------------------------------------------------
    def insert_application(self, app: Application) -> str:
        with self._lock:
            if not app.id:
                app.id = str(uuid4())
            self._applications[app.id] = app.model_copy(deep=True)
            return app.id

    def get_application(self, application_id: str) -> Application | None:
        with self._lock:
            a = self._applications.get(application_id)
            return a.model_copy(deep=True) if a else None

    def list_applications(self, user_id: str, status: ApplicationStatus | None = None) -> list[Application]:
        with self._lock:
            rows = [a.model_copy(deep=True) for a in self._applications.values() if a.user_id == user_id]
            if status:
                rows = [a for a in rows if a.status == status]
            return sorted(rows, key=lambda a: a.created_at, reverse=True)

    def update_application(self, app: Application) -> None:
        with self._lock:
            if app.id in self._applications:
                app.updated_at = datetime.utcnow()
                self._applications[app.id] = app.model_copy(deep=True)

    def list_all_applications(
        self, status: ApplicationStatus | None = None, limit: int = 100
    ) -> list[Application]:
        with self._lock:
            rows = [a.model_copy(deep=True) for a in self._applications.values()]
            if status:
                rows = [a for a in rows if a.status == status]
            rows.sort(key=lambda a: a.created_at, reverse=True)
            return rows[:limit]

    def delete_application(self, application_id: str, user_id: str) -> bool:
        with self._lock:
            a = self._applications.get(application_id)
            if not a or a.user_id != user_id:
                return False
            del self._applications[application_id]
            return True

    # Notifications -----------------------------------------------------
    def insert_notification(self, notification: Notification) -> str:
        with self._lock:
            if not notification.id:
                notification.id = str(uuid4())
            self._notifications[notification.id] = notification.model_copy(deep=True)
            return notification.id

    def list_notifications(self, user_id: str) -> list[Notification]:
        with self._lock:
            rows = [n.model_copy(deep=True) for n in self._notifications.values() if n.user_id == user_id]
            return sorted(rows, key=lambda n: n.created_at, reverse=True)

    def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        with self._lock:
            n = self._notifications.get(notification_id)
            if not n or n.user_id != user_id:
                return False
            n.read_at = datetime.utcnow()
            return True

    def mark_all_notifications_read(self, user_id: str) -> None:
        with self._lock:
            for n in self._notifications.values():
                if n.user_id == user_id and n.read_at is None:
                    n.read_at = datetime.utcnow()

    # Audit -----------------------------------------------------------
    def insert_audit_log(self, log: AuditLog) -> str:
        with self._lock:
            if not log.id:
                log.id = str(uuid4())
            self._audit_logs[log.id] = log.model_copy(deep=True)
            return log.id

    def list_audit_logs(self, limit: int = 100) -> list[AuditLog]:
        with self._lock:
            logs = sorted(self._audit_logs.values(), key=lambda log: log.created_at, reverse=True)
            return [log.model_copy(deep=True) for log in logs[:limit]]

    # AI usage ----------------------------------------------------------
    def insert_ai_usage(self, log: AiUsageLog) -> str:
        with self._lock:
            if not log.id:
                log.id = str(uuid4())
            self._ai_usage[log.id] = log.model_copy(deep=True)
            return log.id

    def count_ai_usage(self, user_id: str, feature: str, since: datetime) -> int:
        with self._lock:
            return sum(
                1
                for log in self._ai_usage.values()
                if log.user_id == user_id and log.feature == feature and log.success and log.created_at >= since
            )

    def list_ai_usage(self, user_id: str | None = None) -> list[AiUsageLog]:
        with self._lock:
            logs = [log.model_copy(deep=True) for log in self._ai_usage.values()]
            if user_id:
                logs = [log for log in logs if log.user_id == user_id]
            return sorted(logs, key=lambda log: log.created_at, reverse=True)

    # Account lifecycle -------------------------------------------------
    def delete_user_data(self, user_id: str) -> None:
        with self._lock:
            self._profiles.pop(user_id, None)
            self._job_prefs.pop(user_id, None)
            self._app_prefs.pop(user_id, None)
            self._notif_prefs.pop(user_id, None)
            self._answer_profiles.pop(user_id, None)
            self._saved.pop(user_id, None)
            for rid, resume in list(self._resumes.items()):
                if resume.user_id == user_id:
                    del self._resumes[rid]
                    self._resume_text.pop(rid, None)
            for vid, version in list(self._resume_versions.items()):
                if version.user_id == user_id:
                    del self._resume_versions[vid]
            for aid, app in list(self._applications.items()):
                if app.user_id == user_id:
                    del self._applications[aid]
            for nid, notif in list(self._notifications.items()):
                if notif.user_id == user_id:
                    del self._notifications[nid]
            for lid, log in list(self._ai_usage.items()):
                if log.user_id == user_id:
                    del self._ai_usage[lid]
            self._admins.discard(user_id)
