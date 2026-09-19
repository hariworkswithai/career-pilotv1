"""Supabase PostgreSQL-backed repository (production).

Implemented over direct PostgreSQL via ``psycopg`` with **parameterized
statements only** (``%s`` placeholders; values are never interpolated into
SQL). One short-lived connection per operation keeps the implementation
thread-safe for FastAPI's sync endpoints and the test client.

Contract notes:
- Mirrors :class:`InMemoryRepository` semantics (dedup by fingerprint,
  ownership checks, soft-delete versions, audit-log retention on account
  deletion).
- Requires migrations ``0001_init``–``0003_search_platform`` applied.
  Full-text search uses the ``search_vector`` column from 0003.
- Credentials: the connection string comes from ``Settings`` resolution
  (``DATABASE_URL``, fallback ``POSTGRES_DSN``) — server-only env vars.
  It is never exposed to the frontend.
- RLS stays in place; the backend connects with the database role from the
  DSN and additionally enforces per-user ownership in every query.
- Migration-0003 features degrade gracefully: full-text search falls back to
  an unindexed ``to_tsvector`` expression when ``search_vector`` is absent,
  and source-health columns are skipped when absent. All other operations
  require only migrations 0001/0002.
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.errors import UndefinedColumn, UniqueViolation
from psycopg.rows import dict_row

from app.core.config import Settings
from app.db.base import Repository
from app.schemas.common import (
    ApplicationStatus,
    ApplyDestination,
    Eligibility,
    EmploymentType,
    ExperienceLevel,
    RemoteScope,
    WorkplaceType,
)
from app.schemas.operations import AiUsageLog, Application, AuditLog, JobSource, Notification
from app.schemas.opportunities import (
    NormalizedLocation,
    NormalizedOpportunity,
    OpportunityFilters,
    OpportunityRecord,
)
from app.schemas.profiles import (
    ApplicationAnswerProfile,
    ApplicationPreferences,
    JobPreferences,
    NotificationPreferences,
    Profile,
)
from app.schemas.resumes import ResumeBase, ResumeVersion

log = logging.getLogger(__name__)

# Prerequisite: migrations 0001_init through 0003_search_platform applied.
REQUIRED_MIGRATIONS = ("0001_init", "0002_phase2", "0003_search_platform")

_OPP_READ_COLUMNS = (
    "id, provider, external_id, source_key, source_id, title, normalized_title,"
    " company_name, location_raw, city, state, country, workplace_type, remote_scope,"
    " description_html, description_text, requirements_html, skills, employment_type,"
    " experience_level, salary_min, salary_max, salary_currency, salary_text, posted_at,"
    " external_url, apply_url, apply_method, india_eligible, eligibility_reason,"
    " is_internship, published, status, dedup_fingerprint, created_at, updated_at"
)

_OPP_MUTABLE_COLUMNS = ["provider", "external_id", "source_key", "source_id", "title", "normalized_title", "company_name", "location_raw", "city", "state", "country", "workplace_type", "remote_scope", "description_html", "description_text", "requirements_html", "skills", "employment_type", "experience_level", "salary_min", "salary_max", "salary_currency", "salary_text", "posted_at", "external_url", "apply_url", "apply_method", "india_eligible", "eligibility_reason", "is_internship", "published"]

# Unindexed full-text document used only when migration 0003's
# search_vector column is absent. Same fields, no A/B/C weighting.
_FTS_FALLBACK_DOCUMENT = (
    "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(company_name, '')"
    " || ' ' || coalesce(description_text, '')"
    " || ' ' || coalesce(array_to_string(skills, ' '), ''))"
)

_SOURCE_COLS_FULL = (
    "id, provider, source_key, company, active, last_synced,"
    " last_sync_status, last_error, created_at"
)
_SOURCE_COLS_BASE = "id, provider, source_key, company, active, last_synced, created_at"

ConnectFactory = Callable[[], Any]


def _utc(value: datetime | None) -> datetime | None:
    """Make naive datetimes explicitly UTC so timestamptz is unambiguous."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _model_fields(model_cls: Any, row: dict[str, Any]) -> dict[str, Any]:
    """Project a DB row onto a pydantic model's fields (tolerates drift)."""
    return {k: v for k, v in row.items() if k in model_cls.model_fields}


class PostgresRepository(Repository):
    """Production PostgreSQL store. Same :class:`Repository` contract as dev."""

    def __init__(
        self,
        settings: Settings | None = None,
        dsn: str | None = None,
        connect: ConnectFactory | None = None,
    ) -> None:
        resolved = dsn or (
            settings.resolved_postgres_dsn if settings is not None else ""
        )
        if not resolved:
            raise ValueError(
                "A database connection string is required for PostgresRepository "
                "(server-only env DATABASE_URL, fallback POSTGRES_DSN)."
            )
        self._dsn = resolved
        # Migration-0003 capability flags. Optimistic by default (canonical
        # schema); flipped permanently on first UndefinedColumn so deployments
        # without 0003 keep working with documented degradations.
        self._use_search_vector = True
        self._source_health_columns = True
        if connect is not None:
            self._connect_factory = connect
        else:
            def _default_connect() -> Any:
                return psycopg.connect(
                    self._dsn, connect_timeout=10, row_factory=dict_row
                )

            self._connect_factory = _default_connect

    # Low-level helpers -------------------------------------------------
    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with self._connect_factory() as conn:
            yield conn

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row is not None else None

    def _all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self._connection() as conn:
            return conn.execute(sql, params).rowcount or 0

    @staticmethod
    def _new_id() -> str:
        return str(uuid4())

    # Access control ----------------------------------------------------
    def is_admin(self, user_id: str) -> bool:
        row = self._one("SELECT 1 AS ok FROM admins WHERE user_id = %s", (user_id,))
        return row is not None

    def set_admin(self, user_id: str, is_admin: bool = True) -> None:
        if is_admin:
            self._exec(
                "INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
                (user_id,),
            )
        else:
            self._exec("DELETE FROM admins WHERE user_id = %s", (user_id,))

    # Opportunities -----------------------------------------------------
    @staticmethod
    def _opp_insert_columns(opp: NormalizedOpportunity, fingerprint: str, source_id: str | None) -> dict[str, Any]:
        data = opp.model_dump(mode="json")
        loc = data.get("location") or {}
        return {
            "provider": data["provider"],
            "external_id": data["external_id"],
            "source_key": data["source_key"],
            "source_id": source_id,
            "title": data["title"],
            "normalized_title": data["normalized_title"],
            "company_name": data["company_name"],
            "location_raw": loc.get("raw", ""),
            "city": loc.get("city"),
            "state": loc.get("state"),
            "country": loc.get("country"),
            "workplace_type": loc.get("workplace_type", "on_site"),
            "remote_scope": loc.get("remote_scope", "none"),
            "description_html": data.get("description_html", ""),
            "description_text": data.get("description_text", ""),
            "requirements_html": data.get("requirements_html", ""),
            "skills": data.get("skills", []),
            "employment_type": data.get("employment_type", "full_time"),
            "experience_level": data.get("experience_level"),
            "salary_min": data.get("salary_min"),
            "salary_max": data.get("salary_max"),
            "salary_currency": data.get("salary_currency"),
            "salary_text": data.get("salary_text"),
            "posted_at": _utc(opp.posted_at),
            "external_url": data.get("external_url", ""),
            "apply_url": data.get("apply_url", ""),
            "apply_method": data.get("apply_method", "continue"),
            "india_eligible": data.get("india_eligible", "ambiguous"),
            "eligibility_reason": data.get("eligibility_reason", ""),
            "is_internship": data.get("is_internship", False),
            "published": data.get("published", True),
            "status": "active",
            "dedup_fingerprint": fingerprint,
        }

    @staticmethod
    def _opp_from_row(row: dict[str, Any]) -> OpportunityRecord:
        location = NormalizedLocation(
            raw=row.get("location_raw") or "",
            city=row.get("city"),
            state=row.get("state"),
            country=row.get("country"),
            workplace_type=WorkplaceType(row.get("workplace_type") or "on_site"),
            remote_scope=RemoteScope(row.get("remote_scope") or "none"),
        )
        kwargs: dict[str, Any] = {
            "id": row["id"],
            "provider": row["provider"],
            "external_id": row["external_id"],
            "source_key": row["source_key"],
            "title": row["title"],
            "normalized_title": row["normalized_title"],
            "company_name": row["company_name"],
            "location": location,
            "description_html": row.get("description_html") or "",
            "description_text": row.get("description_text") or "",
            "requirements_html": row.get("requirements_html") or "",
            "skills": list(row.get("skills") or []),
            "employment_type": EmploymentType(row.get("employment_type") or "full_time"),
            "experience_level": (
                ExperienceLevel(row["experience_level"]) if row.get("experience_level") else None
            ),
            "salary_min": row.get("salary_min"),
            "salary_max": row.get("salary_max"),
            "salary_currency": row.get("salary_currency"),
            "salary_text": row.get("salary_text"),
            "posted_at": row.get("posted_at"),
            "external_url": row.get("external_url") or "",
            "apply_url": row.get("apply_url") or "",
            "apply_method": ApplyDestination(row.get("apply_method") or "continue"),
            "india_eligible": Eligibility(row.get("india_eligible") or "ambiguous"),
            "eligibility_reason": row.get("eligibility_reason") or "",
            "is_internship": bool(row.get("is_internship", False)),
            "published": bool(row.get("published", True)),
            "source_id": row.get("source_id"),
            "status": row.get("status") or "active",
            "dedup_fingerprint": row.get("dedup_fingerprint") or "",
        }
        if row.get("created_at") is not None:
            kwargs["created_at"] = row["created_at"]
        if row.get("updated_at") is not None:
            kwargs["updated_at"] = row["updated_at"]
        return OpportunityRecord(**kwargs)

    def upsert_opportunity(
        self, opp: NormalizedOpportunity, fingerprint: str, source_id: str | None = None
    ) -> tuple[str, bool]:
        cols = self._opp_insert_columns(opp, fingerprint, source_id)
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM opportunities WHERE dedup_fingerprint = %s",
                (fingerprint,),
            ).fetchone()
            if existing is not None:
                update_cols = {k: v for k, v in cols.items() if k != "dedup_fingerprint"}
                set_clause = ", ".join(f"{c} = %s" for c in update_cols)
                params: tuple[Any, ...] = (
                    *update_cols.values(),
                    _utc(datetime.now(UTC)),
                    fingerprint,
                )
                conn.execute(
                    f"UPDATE opportunities SET {set_clause}, updated_at = %s "
                    "WHERE dedup_fingerprint = %s",
                    params,
                )
                return str(existing["id"]), False
            new_id = self._new_id()
            names = ", ".join(["id", *cols.keys()])
            placeholders = ", ".join(["%s"] * (len(cols) + 1))
            conn.execute(
                f"INSERT INTO opportunities ({names}) VALUES ({placeholders})",
                (new_id, *cols.values()),
            )
            return new_id, True

    def get_opportunity(self, opportunity_id: str) -> OpportunityRecord | None:
        row = self._one(
            f"SELECT {_OPP_READ_COLUMNS} FROM opportunities WHERE id = %s",
            (opportunity_id,),
        )
        return self._opp_from_row(row) if row else None

    def _fts_predicate(self, use_vector: bool) -> str:
        if use_vector:
            return "search_vector @@ plainto_tsquery('english', %s)"
        return f"{_FTS_FALLBACK_DOCUMENT} @@ plainto_tsquery('english', %s)"

    def _relevance_order(self, use_vector: bool) -> str:
        if use_vector:
            return (
                "ts_rank(search_vector, plainto_tsquery('english', %s)) DESC,"
                " posted_at DESC NULLS LAST"
            )
        return (
            f"ts_rank({_FTS_FALLBACK_DOCUMENT}, plainto_tsquery('english', %s)) DESC,"
            " posted_at DESC NULLS LAST"
        )

    def _opportunity_filter_clause(
        self, filters: OpportunityFilters, internships_only: bool, use_vector: bool = True
    ) -> tuple[str, list[Any]]:
        where = ["published = TRUE", "status = 'active'"]
        params: list[Any] = []
        where.append("is_internship = %s")
        params.append(bool(internships_only))
        q = filters.q.strip()
        if q:
            where.append(self._fts_predicate(use_vector))
            params.append(q)
        if filters.roles:
            where.append(
                "(" + " OR ".join(["normalized_title ILIKE %s"] * len(filters.roles)) + ")"
            )
            params.extend(f"%{r}%" for r in filters.roles)
        if filters.cities:
            where.append("lower(city) = ANY(%s)")
            params.append([c.lower() for c in filters.cities])
        if filters.work_modes:
            where.append("workplace_type = ANY(%s)")
            params.append([m.value for m in filters.work_modes])
        if filters.experience_levels:
            where.append("experience_level = ANY(%s)")
            params.append([lv.value for lv in filters.experience_levels])
        if filters.employment_types:
            where.append("employment_type = ANY(%s)")
            params.append([t.value for t in filters.employment_types])
        if filters.min_salary is not None:
            where.append("COALESCE(salary_min, 0) >= %s")
            params.append(filters.min_salary)
        if filters.posted_days:
            cutoff = datetime.now(UTC) - timedelta(days=filters.posted_days)
            where.append("COALESCE(posted_at, created_at) >= %s")
            params.append(cutoff)
        return " AND ".join(where), params

    def list_opportunities(
        self,
        filters: OpportunityFilters,
        page: int,
        page_size: int,
        internships_only: bool = False,
    ) -> tuple[list[OpportunityRecord], int]:
        try:
            return self._list_opportunities(filters, page, page_size, internships_only)
        except UndefinedColumn:
            if not self._use_search_vector:
                raise
            log.warning(
                "opportunities.search_vector missing (migration 0003 not applied);"
                " using unindexed full-text fallback for this process."
            )
            self._use_search_vector = False
            return self._list_opportunities(filters, page, page_size, internships_only)

    def _list_opportunities(
        self,
        filters: OpportunityFilters,
        page: int,
        page_size: int,
        internships_only: bool,
    ) -> tuple[list[OpportunityRecord], int]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        clause, params = self._opportunity_filter_clause(
            filters, internships_only, use_vector=self._use_search_vector
        )
        q = filters.q.strip()
        if q and filters.sort != "recent":
            order = self._relevance_order(use_vector=self._use_search_vector)
            order_params: list[Any] = [q]
        else:
            order = "posted_at DESC NULLS LAST, created_at DESC"
            order_params = []
        total_row = self._one(f"SELECT COUNT(*) AS total FROM opportunities WHERE {clause}", tuple(params))
        total = int(total_row["total"]) if total_row else 0
        offset = (page - 1) * page_size
        rows = self._all(
            f"SELECT {_OPP_READ_COLUMNS} FROM opportunities WHERE {clause} "
            f"ORDER BY {order} LIMIT %s OFFSET %s",
            tuple(params) + tuple(order_params) + (page_size, offset),
        )
        return [self._opp_from_row(r) for r in rows], total

    def count_by_source_key(self) -> dict[str, int]:
        rows = self._all("SELECT source_key, COUNT(*) AS n FROM opportunities GROUP BY source_key")
        return {str(r["source_key"]): int(r["n"]) for r in rows}

    def mark_stale_before(self, provider: str, cutoff: datetime) -> int:
        with self._connection() as conn:
            cur = conn.execute(
                "UPDATE opportunities SET status = 'stale', updated_at = %s "
                "WHERE provider = %s AND status = 'active' "
                "AND COALESCE(updated_at, created_at) < %s RETURNING id",
                (_utc(datetime.now(UTC)), provider, _utc(cutoff)),
            )
            return len(cur.fetchall())

    def mark_expired_before(self, cutoff: datetime) -> int:
        with self._connection() as conn:
            cur = conn.execute(
                "UPDATE opportunities SET status = 'expired', updated_at = %s "
                "WHERE status = 'stale' AND COALESCE(updated_at, created_at) < %s RETURNING id",
                (_utc(datetime.now(UTC)), _utc(cutoff)),
            )
            return len(cur.fetchall())

    def list_cities(self) -> list[str]:
        rows = self._all(
            "SELECT DISTINCT lower(btrim(city)) AS city FROM opportunities "
            "WHERE city IS NOT NULL AND btrim(city) <> '' "
            "AND published = TRUE AND status = 'active' ORDER BY 1"
        )
        return [str(r["city"]) for r in rows]

    # Job sources -----------------------------------------------------
    @staticmethod
    def _source_from_row(row: dict[str, Any]) -> JobSource:
        return JobSource(
            id=str(row.get("id") or ""),
            source_type=str(row.get("provider") or ""),
            board_identifier=str(row.get("source_key") or ""),
            company_name=str(row.get("company") or ""),
            is_active=bool(row.get("active", True)),
            last_synced_at=row.get("last_synced"),
            last_sync_status=str(row.get("last_sync_status") or "never"),
            last_error=str(row.get("last_error") or ""),
            created_at=row.get("created_at") or datetime.now(UTC),
        )

    def _source_columns(self) -> str:
        if self._source_health_columns:
            return _SOURCE_COLS_FULL
        return _SOURCE_COLS_BASE

    def _without_source_health_columns(self) -> None:
        if self._source_health_columns:
            log.warning(
                "opportunity_sources health columns missing (migration 0003 not"
                " applied); source sync health tracking degraded for this process."
            )
            self._source_health_columns = False

    def list_sources(self) -> list[JobSource]:
        try:
            rows = self._all(
                f"SELECT {self._source_columns()}"
                " FROM opportunity_sources ORDER BY provider, source_key"
            )
        except UndefinedColumn:
            self._without_source_health_columns()
            rows = self._all(
                f"SELECT {self._source_columns()}"
                " FROM opportunity_sources ORDER BY provider, source_key"
            )
        return [self._source_from_row(r) for r in rows]

    def get_source(self, source_id: str) -> JobSource | None:
        try:
            row = self._one(
                f"SELECT {self._source_columns()}"
                " FROM opportunity_sources WHERE id = %s",
                (source_id,),
            )
        except UndefinedColumn:
            self._without_source_health_columns()
            row = self._one(
                f"SELECT {self._source_columns()}"
                " FROM opportunity_sources WHERE id = %s",
                (source_id,),
            )
        return self._source_from_row(row) if row else None

    def upsert_source(self, source: JobSource) -> str:
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id, company FROM opportunity_sources WHERE provider = %s AND source_key = %s",
                (source.source_type, source.board_identifier),
            ).fetchone()
            if existing is not None:
                company = source.company_name or str(existing["company"] or "")
                conn.execute(
                    "UPDATE opportunity_sources SET company = %s, active = %s WHERE id = %s",
                    (company, source.is_active, existing["id"]),
                )
                return str(existing["id"])
            new_id = source.id or self._new_id()
            if self._source_health_columns:
                try:
                    conn.execute(
                        "INSERT INTO opportunity_sources"
                        " (id, provider, source_key, company, active, last_sync_status, last_error)"
                        " VALUES (%s, %s, %s, %s, %s, 'never', '')",
                        (new_id, source.source_type, source.board_identifier, source.company_name, source.is_active),
                    )
                except UndefinedColumn:
                    conn.rollback()
                    self._without_source_health_columns()
                    conn.execute(
                        "INSERT INTO opportunity_sources"
                        " (id, provider, source_key, company, active)"
                        " VALUES (%s, %s, %s, %s, %s)",
                        (new_id, source.source_type, source.board_identifier, source.company_name, source.is_active),
                    )
            else:
                conn.execute(
                    "INSERT INTO opportunity_sources"
                    " (id, provider, source_key, company, active)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    (new_id, source.source_type, source.board_identifier, source.company_name, source.is_active),
                )
            return new_id

    def set_source_active(self, source_id: str, active: bool) -> bool:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT last_synced FROM opportunity_sources WHERE id = %s", (source_id,)
            ).fetchone()
            if row is None:
                return False
            if not self._source_health_columns:
                conn.execute(
                    "UPDATE opportunity_sources SET active = %s WHERE id = %s",
                    (active, source_id),
                )
                return True
            status = "disabled" if not active else ("never" if row["last_synced"] is None else None)
            if status is None:
                conn.execute(
                    "UPDATE opportunity_sources SET active = %s WHERE id = %s", (active, source_id)
                )
                return True
            try:
                conn.execute(
                    "UPDATE opportunity_sources SET active = %s, last_sync_status = %s WHERE id = %s",
                    (active, status, source_id),
                )
            except UndefinedColumn:
                # The failed statement aborted this transaction; roll back
                # before retrying so the connection stays usable.
                conn.rollback()
                self._without_source_health_columns()
                conn.execute(
                    "UPDATE opportunity_sources SET active = %s WHERE id = %s",
                    (active, source_id),
                )
            return True

    def record_source_sync(self, source_id: str, *, success: bool, error: str = "") -> None:
        if not self._source_health_columns:
            self._exec(
                "UPDATE opportunity_sources SET last_synced = %s WHERE id = %s",
                (_utc(datetime.now(UTC)), source_id),
            )
            return
        try:
            self._exec(
                "UPDATE opportunity_sources SET last_synced = %s,"
                " last_sync_status = %s, last_error = %s WHERE id = %s",
                (
                    _utc(datetime.now(UTC)),
                    "healthy" if success else "failed",
                    "" if success else error[:500],
                    source_id,
                ),
            )
        except UndefinedColumn:
            self._without_source_health_columns()
            self._exec(
                "UPDATE opportunity_sources SET last_synced = %s WHERE id = %s",
                (_utc(datetime.now(UTC)), source_id),
            )

    # Saved -------------------------------------------------------------
    def list_saved(self, user_id: str) -> list[str]:
        rows = self._all(
            "SELECT opportunity_id FROM saved_opportunities WHERE user_id = %s ORDER BY saved_at DESC",
            (user_id,),
        )
        return sorted({str(r["opportunity_id"]) for r in rows})

    def add_saved(self, user_id: str, opportunity_id: str) -> None:
        with contextlib.suppress(UniqueViolation):  # idempotent save
            self._exec(
                "INSERT INTO saved_opportunities (user_id, opportunity_id) VALUES (%s, %s)",
                (user_id, opportunity_id),
            )

    def remove_saved(self, user_id: str, opportunity_id: str) -> None:
        self._exec(
            "DELETE FROM saved_opportunities WHERE user_id = %s AND opportunity_id = %s",
            (user_id, opportunity_id),
        )

    # Profile & preferences --------------------------------------------
    def get_profile(self, user_id: str) -> Profile | None:
        row = self._one("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
        return Profile(**_model_fields(Profile, row)) if row else None

    def list_profiles(self, limit: int = 100) -> list[Profile]:
        rows = self._all(
            "SELECT * FROM profiles ORDER BY created_at DESC LIMIT %s", (max(1, limit),)
        )
        return [Profile(**_model_fields(Profile, r)) for r in rows]

    def upsert_profile(self, profile: Profile) -> None:
        data = profile.model_dump(mode="json")
        self._exec(
            "INSERT INTO profiles"
            " (user_id, full_name, headline, phone, city, state, education, experience,"
            "  projects, skills, resume_completeness, onboarding_completed)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (user_id) DO UPDATE SET"
            " full_name = EXCLUDED.full_name, headline = EXCLUDED.headline,"
            " phone = EXCLUDED.phone, city = EXCLUDED.city, state = EXCLUDED.state,"
            " education = EXCLUDED.education, experience = EXCLUDED.experience,"
            " projects = EXCLUDED.projects, skills = EXCLUDED.skills,"
            " resume_completeness = EXCLUDED.resume_completeness,"
            " onboarding_completed = EXCLUDED.onboarding_completed,"
            " updated_at = %s",
            (
                data["user_id"], data.get("full_name", ""), data.get("headline", ""),
                data.get("phone", ""), data.get("city", ""), data.get("state", ""),
                json.dumps(data.get("education", [])), json.dumps(data.get("experience", [])),
                json.dumps(data.get("projects", [])), data.get("skills", []),
                data.get("resume_completeness", 0), data.get("onboarding_completed", False),
                _utc(datetime.now(UTC)),
            ),
        )

    def get_job_preferences(self, user_id: str) -> JobPreferences | None:
        row = self._one("SELECT * FROM job_preferences WHERE user_id = %s", (user_id,))
        return JobPreferences(**_model_fields(JobPreferences, row)) if row else None

    def upsert_job_preferences(self, prefs: JobPreferences) -> None:
        data = prefs.model_dump(mode="json")
        self._exec(
            "INSERT INTO job_preferences"
            " (user_id, target_roles, preferred_cities, preferred_states, work_modes,"
            "  experience_level, employment_types, salary_min, salary_max, remote_ok)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (user_id) DO UPDATE SET"
            " target_roles = EXCLUDED.target_roles, preferred_cities = EXCLUDED.preferred_cities,"
            " preferred_states = EXCLUDED.preferred_states, work_modes = EXCLUDED.work_modes,"
            " experience_level = EXCLUDED.experience_level,"
            " employment_types = EXCLUDED.employment_types, salary_min = EXCLUDED.salary_min,"
            " salary_max = EXCLUDED.salary_max, remote_ok = EXCLUDED.remote_ok,"
            " updated_at = %s",
            (
                data["user_id"], data.get("target_roles", []), data.get("preferred_cities", []),
                data.get("preferred_states", []), data.get("work_modes", []),
                data.get("experience_level"), data.get("employment_types", []),
                data.get("salary_min"), data.get("salary_max"), data.get("remote_ok", False),
                _utc(datetime.now(UTC)),
            ),
        )

    def get_application_preferences(self, user_id: str) -> ApplicationPreferences | None:
        row = self._one("SELECT * FROM application_preferences WHERE user_id = %s", (user_id,))
        return ApplicationPreferences(**_model_fields(ApplicationPreferences, row)) if row else None

    def upsert_application_preferences(self, prefs: ApplicationPreferences) -> None:
        data = prefs.model_dump(mode="json")
        self._exec(
            "INSERT INTO application_preferences"
            " (user_id, default_resume_id, default_application_profile_id,"
            "  autofill_enabled, confirm_before_submit)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (user_id) DO UPDATE SET"
            " default_resume_id = EXCLUDED.default_resume_id,"
            " default_application_profile_id = EXCLUDED.default_application_profile_id,"
            " autofill_enabled = EXCLUDED.autofill_enabled,"
            " confirm_before_submit = EXCLUDED.confirm_before_submit,"
            " updated_at = %s",
            (
                data["user_id"], data.get("default_resume_id"),
                data.get("default_application_profile_id"),
                data.get("autofill_enabled", True), data.get("confirm_before_submit", True),
                _utc(datetime.now(UTC)),
            ),
        )

    def get_notification_preferences(self, user_id: str) -> NotificationPreferences | None:
        row = self._one("SELECT * FROM notification_preferences WHERE user_id = %s", (user_id,))
        return NotificationPreferences(**_model_fields(NotificationPreferences, row)) if row else None

    def upsert_notification_preferences(self, prefs: NotificationPreferences) -> None:
        data = prefs.model_dump(mode="json")
        self._exec(
            "INSERT INTO notification_preferences"
            " (user_id, matching_jobs, internships, application_updates, resume_suggestions)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (user_id) DO UPDATE SET"
            " matching_jobs = EXCLUDED.matching_jobs, internships = EXCLUDED.internships,"
            " application_updates = EXCLUDED.application_updates,"
            " resume_suggestions = EXCLUDED.resume_suggestions,"
            " updated_at = %s",
            (
                data["user_id"], data.get("matching_jobs", True), data.get("internships", True),
                data.get("application_updates", True), data.get("resume_suggestions", True),
                _utc(datetime.now(UTC)),
            ),
        )

    def get_answer_profile(self, user_id: str) -> ApplicationAnswerProfile | None:
        row = self._one("SELECT * FROM application_answer_profiles WHERE user_id = %s", (user_id,))
        return ApplicationAnswerProfile(**_model_fields(ApplicationAnswerProfile, row)) if row else None

    def upsert_answer_profile(self, profile: ApplicationAnswerProfile) -> None:
        data = profile.model_dump(mode="json")
        self._exec(
            "INSERT INTO application_answer_profiles"
            " (user_id, name, email, phone, work_experience, education, skills, links, confirmed_fields)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (user_id) DO UPDATE SET"
            " name = EXCLUDED.name, email = EXCLUDED.email, phone = EXCLUDED.phone,"
            " work_experience = EXCLUDED.work_experience, education = EXCLUDED.education,"
            " skills = EXCLUDED.skills, links = EXCLUDED.links,"
            " confirmed_fields = EXCLUDED.confirmed_fields,"
            " updated_at = %s",
            (
                data["user_id"], data.get("name", ""), data.get("email"), data.get("phone", ""),
                json.dumps(data.get("work_experience", [])), json.dumps(data.get("education", [])),
                data.get("skills", []), data.get("links", []), data.get("confirmed_fields", []),
                _utc(datetime.now(UTC)),
            ),
        )

    # Resumes -----------------------------------------------------------
    def insert_resume(self, resume: ResumeBase) -> str:
        data = resume.model_dump(mode="json")
        new_id = data.get("id") or self._new_id()
        self._exec(
            "INSERT INTO resumes"
            " (id, user_id, original_filename, stored_filename, file_type, file_size,"
            "  parse_status, parse_error, parsed_data)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                new_id, data["user_id"], data.get("original_filename", ""),
                data.get("stored_filename", ""), data.get("file_type", ""),
                data.get("file_size", 0), data.get("parse_status", "pending"),
                data.get("parse_error"), json.dumps(data.get("parsed_data", {})),
            ),
        )
        return new_id

    def get_resume(self, resume_id: str) -> ResumeBase | None:
        row = self._one("SELECT * FROM resumes WHERE id = %s", (resume_id,))
        return ResumeBase(**_model_fields(ResumeBase, row)) if row else None

    def list_resumes(self, user_id: str) -> list[ResumeBase]:
        rows = self._all(
            "SELECT * FROM resumes WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
        )
        return [ResumeBase(**_model_fields(ResumeBase, r)) for r in rows]

    def delete_resume(self, resume_id: str, user_id: str) -> bool:
        return (
            self._exec(
                "DELETE FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id)
            )
            > 0
        )

    def save_resume_parsed(self, resume_id: str, parsed: dict) -> None:
        self._exec(
            "UPDATE resumes SET parsed_data = %s, parse_status = 'parsed' WHERE id = %s",
            (json.dumps(parsed), resume_id),
        )

    def insert_resume_version(self, version: ResumeVersion) -> str:
        data = version.model_dump(mode="json")
        new_id = data.get("id") or self._new_id()
        self._exec(
            "INSERT INTO resume_versions"
            " (id, user_id, parent_resume_id, target_opportunity_id, version_label,"
            "  version_number, stored_filename, file_type, status, parsed_data,"
            "  enhancement_metadata)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                new_id, data["user_id"], data.get("parent_resume_id"),
                data.get("target_opportunity_id"), data.get("version_label", ""),
                data.get("version_number", 1), data.get("stored_filename", ""),
                data.get("file_type", ""), data.get("status", "active"),
                json.dumps(data.get("parsed_data", {})),
                json.dumps(data.get("enhancement_metadata", {})),
            ),
        )
        return new_id

    def get_resume_version(self, version_id: str) -> ResumeVersion | None:
        row = self._one("SELECT * FROM resume_versions WHERE id = %s", (version_id,))
        return ResumeVersion(**_model_fields(ResumeVersion, row)) if row else None

    def list_resume_versions(self, parent_resume_id: str) -> list[ResumeVersion]:
        rows = self._all(
            "SELECT * FROM resume_versions"
            " WHERE parent_resume_id = %s AND status = 'active' ORDER BY version_number",
            (parent_resume_id,),
        )
        return [ResumeVersion(**_model_fields(ResumeVersion, r)) for r in rows]

    def archive_resume_version(self, version_id: str, user_id: str) -> bool:
        with self._connection() as conn:
            owner = conn.execute(
                "SELECT user_id FROM resume_versions WHERE id = %s", (version_id,)
            ).fetchone()
            if owner is None or str(owner["user_id"]) != user_id:
                return False
            used = conn.execute(
                "SELECT 1 FROM applications WHERE resume_version_id = %s LIMIT 1",
                (version_id,),
            ).fetchone()
            if used is not None:
                return False
            conn.execute(
                "UPDATE resume_versions SET status = 'archived' WHERE id = %s", (version_id,)
            )
            return True

    def application_uses_resume_version(self, version_id: str) -> bool:
        row = self._one(
            "SELECT 1 AS ok FROM applications WHERE resume_version_id = %s LIMIT 1",
            (version_id,),
        )
        return row is not None

    # Applications ------------------------------------------------------
    def insert_application(self, app: Application) -> str:
        data = app.model_dump(mode="json")
        new_id = data.get("id") or self._new_id()
        self._exec(
            "INSERT INTO applications"
            " (id, user_id, opportunity_id, company_snapshot, role_snapshot, status,"
            "  applied_at, resume_version_id, destination, destination_url, notes, answer_summary)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                new_id, data["user_id"], data["opportunity_id"],
                json.dumps(data.get("company_snapshot", {})),
                json.dumps(data.get("role_snapshot", {})),
                data.get("status", ApplicationStatus.SAVED.value),
                _utc(app.applied_at), data.get("resume_version_id"),
                data.get("destination", "continue"), data.get("destination_url", ""),
                data.get("notes", ""), json.dumps(data.get("answer_summary", {})),
            ),
        )
        return new_id

    def get_application(self, application_id: str) -> Application | None:
        row = self._one("SELECT * FROM applications WHERE id = %s", (application_id,))
        return Application(**_model_fields(Application, row)) if row else None

    def list_applications(
        self, user_id: str, status: ApplicationStatus | None = None
    ) -> list[Application]:
        if status is None:
            rows = self._all(
                "SELECT * FROM applications WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
        else:
            rows = self._all(
                "SELECT * FROM applications WHERE user_id = %s AND status = %s"
                " ORDER BY created_at DESC",
                (user_id, status.value),
            )
        return [Application(**_model_fields(Application, r)) for r in rows]

    def list_all_applications(
        self, status: ApplicationStatus | None = None, limit: int = 100
    ) -> list[Application]:
        if status is None:
            rows = self._all(
                "SELECT * FROM applications ORDER BY created_at DESC LIMIT %s",
                (max(1, limit),),
            )
        else:
            rows = self._all(
                "SELECT * FROM applications WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                (status.value, max(1, limit)),
            )
        return [Application(**_model_fields(Application, r)) for r in rows]

    def update_application(self, app: Application) -> None:
        data = app.model_dump(mode="json")
        self._exec(
            "UPDATE applications SET company_snapshot = %s, role_snapshot = %s, status = %s,"
            " applied_at = %s, resume_version_id = %s, destination = %s, destination_url = %s,"
            " notes = %s, answer_summary = %s, updated_at = %s WHERE id = %s",
            (
                json.dumps(data.get("company_snapshot", {})),
                json.dumps(data.get("role_snapshot", {})),
                data.get("status", ApplicationStatus.SAVED.value),
                _utc(app.applied_at), data.get("resume_version_id"),
                data.get("destination", "continue"), data.get("destination_url", ""),
                data.get("notes", ""), json.dumps(data.get("answer_summary", {})),
                _utc(datetime.now(UTC)), data["id"],
            ),
        )

    def delete_application(self, application_id: str, user_id: str) -> bool:
        return (
            self._exec(
                "DELETE FROM applications WHERE id = %s AND user_id = %s",
                (application_id, user_id),
            )
            > 0
        )

    # Notifications -----------------------------------------------------
    def insert_notification(self, notification: Notification) -> str:
        data = notification.model_dump(mode="json")
        if data.get("id"):
            self._exec(
                "INSERT INTO notifications (id, user_id, type, title, body) VALUES (%s, %s, %s, %s, %s)",
                (data["id"], data["user_id"], data.get("type", ""),
                 data.get("title", ""), data.get("body", "")),
            )
            return str(data["id"])
        with self._connection() as conn:
            row = conn.execute(
                "INSERT INTO notifications (user_id, type, title, body)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                (data["user_id"], data.get("type", ""), data.get("title", ""), data.get("body", "")),
            ).fetchone()
            return str(row["id"])

    def list_notifications(self, user_id: str) -> list[Notification]:
        rows = self._all(
            "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
        )
        return [Notification(**_model_fields(Notification, r)) for r in rows]

    def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        return (
            self._exec(
                "UPDATE notifications SET read_at = %s WHERE id = %s AND user_id = %s",
                (_utc(datetime.now(UTC)), notification_id, user_id),
            )
            > 0
        )

    def mark_all_notifications_read(self, user_id: str) -> None:
        self._exec(
            "UPDATE notifications SET read_at = %s WHERE user_id = %s AND read_at IS NULL",
            (_utc(datetime.now(UTC)), user_id),
        )

    # Audit -----------------------------------------------------------
    def insert_audit_log(self, log: AuditLog) -> str:
        data = log.model_dump(mode="json")
        if data.get("id"):
            self._exec(
                "INSERT INTO audit_logs"
                " (id, actor_user_id, action, resource_type, resource_id, metadata,"
                "  ip_address, user_agent)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    data["id"], data["actor_user_id"], data.get("action", ""),
                    data.get("resource_type", ""), data.get("resource_id", ""),
                    json.dumps(data.get("metadata", {})),
                    data.get("ip_address", ""), data.get("user_agent", ""),
                ),
            )
            return str(data["id"])
        with self._connection() as conn:
            row = conn.execute(
                "INSERT INTO audit_logs"
                " (actor_user_id, action, resource_type, resource_id, metadata,"
                "  ip_address, user_agent)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    data["actor_user_id"], data.get("action", ""),
                    data.get("resource_type", ""), data.get("resource_id", ""),
                    json.dumps(data.get("metadata", {})),
                    data.get("ip_address", ""), data.get("user_agent", ""),
                ),
            ).fetchone()
            return str(row["id"])

    def list_audit_logs(self, limit: int = 100) -> list[AuditLog]:
        rows = self._all(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT %s", (max(1, limit),)
        )
        return [AuditLog(**_model_fields(AuditLog, r)) for r in rows]

    # AI usage ----------------------------------------------------------
    def insert_ai_usage(self, log: AiUsageLog) -> str:
        data = log.model_dump(mode="json")
        if data.get("id"):
            self._exec(
                "INSERT INTO ai_usage_logs"
                " (id, user_id, feature, model, tokens_input, tokens_output,"
                "  cost_usd, success, error)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    data["id"], data["user_id"], data.get("feature", ""),
                    data.get("model", ""), data.get("tokens_input", 0),
                    data.get("tokens_output", 0), data.get("cost_usd", 0.0),
                    data.get("success", True), data.get("error", ""),
                ),
            )
            return str(data["id"])
        with self._connection() as conn:
            row = conn.execute(
                "INSERT INTO ai_usage_logs"
                " (user_id, feature, model, tokens_input, tokens_output,"
                "  cost_usd, success, error)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    data["user_id"], data.get("feature", ""), data.get("model", ""),
                    data.get("tokens_input", 0), data.get("tokens_output", 0),
                    data.get("cost_usd", 0.0), data.get("success", True),
                    data.get("error", ""),
                ),
            ).fetchone()
            return str(row["id"])

    def count_ai_usage(self, user_id: str, feature: str, since: datetime) -> int:
        row = self._one(
            "SELECT COUNT(*) AS n FROM ai_usage_logs"
            " WHERE user_id = %s AND feature = %s AND success = TRUE AND created_at >= %s",
            (user_id, feature, _utc(since)),
        )
        return int(row["n"]) if row else 0

    def list_ai_usage(self, user_id: str | None = None) -> list[AiUsageLog]:
        if user_id:
            rows = self._all(
                "SELECT * FROM ai_usage_logs WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
        else:
            rows = self._all("SELECT * FROM ai_usage_logs ORDER BY created_at DESC")
        return [AiUsageLog(**_model_fields(AiUsageLog, r)) for r in rows]

    # Account lifecycle -------------------------------------------------
    def delete_user_data(self, user_id: str) -> None:
        """Remove every user-owned row in one transaction.

        Audit logs are intentionally retained (compliance trail); the catalog
        (opportunities) is shared and never deleted.
        """
        tables = (
            "applications",
            "saved_opportunities",
            "resume_versions",
            "resumes",
            "notifications",
            "ai_usage_logs",
            "job_preferences",
            "application_preferences",
            "notification_preferences",
            "application_answer_profiles",
            "profiles",
            "admins",
        )
        with self._connection() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))

    def ping(self) -> bool:
        try:
            row = self._one("SELECT 1 AS ok")
            return row is not None
        except Exception:  # noqa: BLE001 - ping must never raise
            log.warning("PostgresRepository.ping failed", exc_info=True)
            return False
