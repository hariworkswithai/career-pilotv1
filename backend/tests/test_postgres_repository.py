"""PostgresRepository integration tests against a fake psycopg connection.

No live database is required: a scripted in-memory connection records every
(SQL, params) pair so tests verify parameterized statements, ownership
filters, pagination, and row mapping without touching Supabase.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from psycopg.errors import UniqueViolation

from app.db import PostgresRepository
from app.db.base import Repository
from app.schemas.common import ApplicationStatus
from app.schemas.operations import Application, JobSource
from app.schemas.opportunities import OpportunityFilters
from tests.helpers import make_opportunity, make_profile


class FakeCursor:
    def __init__(self, response: Any) -> None:
        self._response = response

    def fetchone(self) -> Any:
        assert isinstance(self._response, tuple) and self._response[0] == "one"
        return self._response[1]

    def fetchall(self) -> Any:
        assert isinstance(self._response, tuple) and self._response[0] == "all"
        return self._response[1]

    @property
    def rowcount(self) -> int:
        assert isinstance(self._response, tuple) and self._response[0] == "rc"
        return self._response[1]


class FakeConnection:
    """Scripted stand-in for a psycopg connection (context-manager protocol)."""

    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.statements: list[tuple[str, tuple[Any, ...]]] = []
        self.opens = 0

    def __enter__(self) -> FakeConnection:
        self.opens += 1
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> FakeCursor:
        self.statements.append((sql, tuple(params)))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return FakeCursor(response)

    def rollback(self) -> None:
        self.statements.append(("ROLLBACK", ()))


def make_repo(*responses: Any) -> tuple[PostgresRepository, FakeConnection]:
    conn = FakeConnection(*responses)
    repo = PostgresRepository(dsn="postgresql://test:test@localhost:5432/test", connect=lambda: conn)
    return repo, conn


def opp_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "id": "opp-1",
        "provider": "greenhouse",
        "external_id": "e1",
        "source_key": "acme",
        "source_id": None,
        "title": "Backend Engineer",
        "normalized_title": "backend engineer",
        "company_name": "Acme",
        "location_raw": "Bengaluru, India",
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "India",
        "workplace_type": "on_site",
        "remote_scope": "none",
        "description_html": "",
        "description_text": "Build APIs",
        "requirements_html": "",
        "skills": ["python"],
        "employment_type": "full_time",
        "experience_level": "mid",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_text": None,
        "posted_at": None,
        "external_url": "https://example.com/1",
        "apply_url": "https://example.com/1",
        "apply_method": "continue",
        "india_eligible": "eligible",
        "eligibility_reason": "",
        "is_internship": False,
        "published": True,
        "status": "active",
        "dedup_fingerprint": "fp-1",
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 2, tzinfo=UTC),
    }
    row.update(overrides)
    return row


class TestInterfacePreserved:
    def test_implements_full_protocol(self):
        proto_methods = {
            name
            for name, member in Repository.__dict__.items()
            if callable(member) and not name.startswith("_")
        }
        missing = [m for m in proto_methods if not callable(getattr(PostgresRepository, m, None))]
        assert missing == []

    def test_signatures_match_protocol(self):
        import inspect

        mismatched = []
        for name, member in Repository.__dict__.items():
            if not callable(member) or name.startswith("_"):
                continue
            expected = list(inspect.signature(member).parameters)[1:]  # drop self
            actual = list(inspect.signature(getattr(PostgresRepository, name)).parameters)[1:]
            if expected != actual:
                mismatched.append(name)
        assert mismatched == []


class TestWiring:
    def test_dsn_required(self):
        with pytest.raises(ValueError, match="DATABASE_URL"):
            PostgresRepository(dsn="")

    def test_dsn_from_settings(self):
        from app.core.config import Settings

        repo = PostgresRepository(settings=Settings(postgres_dsn="postgresql://x"))
        assert repo._dsn == "postgresql://x"

    def test_database_url_takes_precedence_over_legacy_dsn(self):
        from app.core.config import Settings

        repo = PostgresRepository(
            settings=Settings(database_url="postgresql://canonical", postgres_dsn="postgresql://legacy")
        )
        assert repo._dsn == "postgresql://canonical"

    def test_explicit_dsn_wins(self):
        from app.core.config import Settings

        repo = PostgresRepository(settings=Settings(postgres_dsn="postgresql://a"), dsn="postgresql://b")
        assert repo._dsn == "postgresql://b"

    def test_build_repository_gate(self, monkeypatch):
        from app.core.config import get_settings
        from app.db import InMemoryRepository, build_repository

        monkeypatch.setenv("REPOSITORY_BACKEND", "postgres")
        monkeypatch.setenv("POSTGRES_DSN", "postgresql://u:p@localhost:5432/db")
        get_settings.cache_clear()
        try:
            assert isinstance(build_repository(), PostgresRepository)
        finally:
            get_settings.cache_clear()

        monkeypatch.delenv("POSTGRES_DSN")
        get_settings.cache_clear()
        try:
            assert isinstance(build_repository(), InMemoryRepository)
        finally:
            get_settings.cache_clear()

    def test_build_repository_gate_prefers_database_url(self, monkeypatch):
        from app.core.config import get_settings
        from app.db import build_repository

        monkeypatch.setenv("REPOSITORY_BACKEND", "postgres")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
        monkeypatch.delenv("POSTGRES_DSN", raising=False)
        get_settings.cache_clear()
        try:
            assert isinstance(build_repository(), PostgresRepository)
        finally:
            get_settings.cache_clear()

    def test_ping_true_and_false(self):
        repo, _ = make_repo(("one", {"ok": 1}))
        assert repo.ping() is True

        def boom() -> Any:
            raise OSError("no network")

        down = PostgresRepository(dsn="postgresql://x", connect=boom)
        assert down.ping() is False


class TestOpportunities:
    def test_upsert_insert_path(self):
        repo, conn = make_repo(("one", None), ("rc", 1))
        opp_id, created = repo.upsert_opportunity(make_opportunity(), "fp-1", None)
        assert created is True
        assert opp_id
        select_sql, select_params = conn.statements[0]
        assert "dedup_fingerprint = %s" in select_sql
        assert select_params == ("fp-1",)
        insert_sql, insert_params = conn.statements[1]
        assert insert_sql.startswith("INSERT INTO opportunities")
        assert "%s" in insert_sql
        assert "fp-1" in insert_params
        assert opp_id in insert_params

    def test_upsert_update_preserves_identity(self):
        repo, conn = make_repo(("one", {"id": "existing-id"}), ("rc", 1))
        opp_id, created = repo.upsert_opportunity(make_opportunity(), "fp-1", "src-9")
        assert (opp_id, created) == ("existing-id", False)
        update_sql, update_params = conn.statements[1]
        assert update_sql.startswith("UPDATE opportunities SET")
        assert "status" in update_sql and "updated_at" in update_sql
        set_part = update_sql.split("WHERE")[0]
        assert "created_at" not in set_part  # first-seen timestamp preserved
        assert "dedup_fingerprint" not in set_part
        assert update_params[-1] == "fp-1"
        assert "src-9" in update_params

    def test_get_maps_nested_location_and_enums(self):
        repo, _ = make_repo(("one", opp_row()))
        rec = repo.get_opportunity("opp-1")
        assert rec is not None
        assert rec.location.city == "Bengaluru"
        assert rec.location.workplace_type.value == "on_site"
        assert rec.employment_type.value == "full_time"
        assert rec.skills == ["python"]
        assert rec.is_active is True

    def test_get_missing_returns_none(self):
        repo, _ = make_repo(("one", None))
        assert repo.get_opportunity("nope") is None

    def test_list_paginates_with_count(self):
        repo, conn = make_repo(("one", {"total": 42}), ("all", [opp_row(), opp_row()]))
        items, total = repo.list_opportunities(OpportunityFilters(), page=2, page_size=20)
        assert total == 42
        assert len(items) == 2
        list_sql, list_params = conn.statements[1]
        assert list_params[-2:] == (20, 20)  # LIMIT %s OFFSET %s
        assert "LIMIT %s OFFSET %s" in list_sql

    def test_list_full_text_search_is_parameterized(self):
        repo, conn = make_repo(("one", {"total": 0}), ("all", []))
        attack = "x' OR '1'='1"
        repo.list_opportunities(OpportunityFilters(q=attack), page=1, page_size=10)
        list_sql, list_params = conn.statements[1]
        assert "search_vector @@ plainto_tsquery('english', %s)" in list_sql
        assert "ts_rank" in list_sql
        assert attack not in list_sql  # value travels only in params
        assert attack in list_params

    def test_list_recent_sort_and_filters(self):
        repo, conn = make_repo(("one", {"total": 0}), ("all", []))
        repo.list_opportunities(
            OpportunityFilters(
                cities=["Bengaluru"], work_modes=[], sort="recent", min_salary=500000, posted_days=7
            ),
            page=1,
            page_size=10,
        )
        list_sql, list_params = conn.statements[1]
        assert "posted_at DESC NULLS LAST" in list_sql
        assert "lower(city) = ANY(%s)" in list_sql
        assert "COALESCE(salary_min, 0) >= %s" in list_sql
        assert "COALESCE(posted_at, created_at) >= %s" in list_sql
        assert ["bengaluru"] in list_params
        assert 500000 in list_params

    def test_mark_stale_and_expired_count_returned_rows(self):
        repo, _ = make_repo(("all", [{"id": "a"}, {"id": "b"}]))
        from datetime import datetime as dt

        assert repo.mark_stale_before("greenhouse", dt.now(UTC)) == 2
        repo2, conn2 = make_repo(("all", [{"id": "a"}]))
        from datetime import datetime as dt2

        assert repo2.mark_expired_before(dt2.now(UTC)) == 1
        assert "status = 'stale'" in conn2.statements[0][0]

    def test_count_by_source_key(self):
        repo, _ = make_repo(("all", [{"source_key": "acme", "n": 3}]))
        assert repo.count_by_source_key() == {"acme": 3}

    def test_list_cities(self):
        repo, _ = make_repo(("all", [{"city": "bengaluru"}, {"city": "mumbai"}]))
        assert repo.list_cities() == ["bengaluru", "mumbai"]


class TestSourcesSavedAdmin:
    def test_source_round_trip_mapping(self):
        repo, _ = make_repo(
            ("all", [{
                "id": "s1", "provider": "greenhouse", "source_key": "acme",
                "company": "Acme", "active": True, "last_synced": None,
                "last_sync_status": "never", "last_error": "",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            }])
        )
        (source,) = repo.list_sources()
        assert source.source_type == "greenhouse"
        assert source.board_identifier == "acme"
        assert source.company_name == "Acme"

    def test_upsert_source_update_path(self):
        repo, conn = make_repo(("one", {"id": "s1", "company": "Old"}), ("rc", 1))
        assert repo.upsert_source(JobSource(source_type="g", board_identifier="b", company_name="New")) == "s1"
        assert "UPDATE opportunity_sources SET" in conn.statements[1][0]

    def test_upsert_source_insert_path(self):
        repo, conn = make_repo(("one", None), ("rc", 1))
        new_id = repo.upsert_source(JobSource(source_type="g", board_identifier="b"))
        assert new_id
        assert conn.statements[1][0].startswith("INSERT INTO opportunity_sources")

    def test_set_source_active_paths(self):
        repo, _ = make_repo(("one", {"last_synced": None}), ("rc", 1))
        assert repo.set_source_active("s1", False) is True
        repo2, _ = make_repo(("one", None))
        assert repo2.set_source_active("missing", True) is False

    def test_record_source_sync_truncates_error(self):
        repo, conn = make_repo(("rc", 1))
        repo.record_source_sync("s1", success=False, error="x" * 900)
        assert conn.statements[0][1][2] == "x" * 500
        assert conn.statements[0][1][1] == "failed"

    def test_saved_add_duplicate_swallowed(self):
        repo, _ = make_repo(UniqueViolation("duplicate key"))
        assert repo.add_saved("u1", "o1") is None  # idempotent, no raise

    def test_saved_list_sorted(self):
        repo, _ = make_repo(("all", [{"opportunity_id": "b"}, {"opportunity_id": "a"}]))
        assert repo.list_saved("u1") == ["a", "b"]

    def test_admin_round_trip(self):
        repo, conn = make_repo(("one", {"ok": 1}), ("rc", 1), ("rc", 1))
        assert repo.is_admin("u1") is True
        repo.set_admin("u2", True)
        assert "ON CONFLICT (user_id) DO NOTHING" in conn.statements[-1][0]
        repo.set_admin("u2", False)
        assert conn.statements[-1][0].startswith("DELETE FROM admins")

    def test_audit_insert_uses_returning_id(self):
        from app.schemas.operations import AuditLog

        repo, _ = make_repo(("one", {"id": "audit-9"}))
        assert repo.insert_audit_log(AuditLog(actor_user_id="u", action="a.b")) == "audit-9"

    def test_audit_list_limit_parameterized(self):
        repo, conn = make_repo(("all", []))
        repo.list_audit_logs(limit=25)
        assert conn.statements[0][1] == (25,)


class TestUserEntities:
    def test_profile_round_trip_tolerates_missing_columns(self):
        repo, _ = make_repo(("one", {"user_id": "u1", "full_name": "Ada", "skills": ["go"]}))
        profile = repo.get_profile("u1")
        assert profile is not None
        assert profile.full_name == "Ada"
        assert profile.email == ""  # no email column in DB
        assert profile.onboarding_completed is False

    def test_profile_upsert_conflict(self):
        repo, conn = make_repo(("rc", 1))
        repo.upsert_profile(make_profile(user_id="u1"))
        assert "ON CONFLICT (user_id) DO UPDATE" in conn.statements[0][0]

    def test_application_lifecycle_statements(self):
        repo, conn = make_repo(
            ("rc", 1),
            ("one", {"id": "a1", "user_id": "u1", "opportunity_id": "o1"}),
            ("rc", 1),
        )
        app = Application(id="", user_id="u1", opportunity_id="o1")
        new_id = repo.insert_application(app)
        assert new_id
        assert conn.statements[0][0].startswith("INSERT INTO applications")
        assert repo.get_application("a1") is not None
        assert repo.delete_application("a1", "u2") is True
        delete_sql, delete_params = conn.statements[-1]
        assert "user_id = %s" in delete_sql  # ownership enforced in SQL
        assert delete_params == ("a1", "u2")

    def test_application_list_scoped_and_ordered(self):
        repo, conn = make_repo(("all", []))
        repo.list_applications("u1", ApplicationStatus.APPLIED)
        sql, params = conn.statements[0]
        assert "user_id = %s AND status = %s" in sql
        assert params == ("u1", "applied")
        assert "ORDER BY created_at DESC" in sql

    def test_notifications_and_ai_usage(self):
        from app.schemas.operations import Notification

        repo, conn = make_repo(
            ("one", {"id": "n1"}), ("all", []), ("rc", 1),
            ("one", {"n": 2}), ("all", []),
        )
        assert repo.insert_notification(Notification(id="", user_id="u1", type="t", title="t")) == "n1"
        assert repo.list_notifications("u1") == []
        assert repo.mark_notification_read("n1", "u1") is True
        assert repo.count_ai_usage("u1", "enhancement", datetime.now(UTC)) == 2
        count_sql, count_params = conn.statements[3]
        assert "success = TRUE" in count_sql and "created_at >= %s" in count_sql
        assert count_params[1] == "enhancement"
        assert repo.list_ai_usage("u1") == []
        list_sql, list_params = conn.statements[4]
        assert "WHERE user_id = %s" in list_sql

    def test_archive_version_guards_history(self):

        repo, _ = make_repo(("one", {"user_id": "u1"}), ("one", {"ok": 1}))
        assert repo.archive_resume_version("v1", "u1") is False  # used by application

        repo2, conn2 = make_repo(("one", {"user_id": "u1"}), ("one", None), ("rc", 1))
        assert repo2.archive_resume_version("v1", "u1") is True
        assert "status = 'archived'" in conn2.statements[-1][0]

        repo3, _ = make_repo(("one", {"user_id": "other"}))
        assert repo3.archive_resume_version("v1", "u1") is False  # not the owner

    def test_resume_crud_statements(self):
        from app.schemas.resumes import ResumeBase

        repo, conn = make_repo(("rc", 1), ("one", None), ("rc", 1), ("rc", 1))
        resume = ResumeBase(
            id="", user_id="u1", original_filename="a.pdf",
            stored_filename="b.pdf", file_type="pdf", file_size=10,
        )
        assert repo.insert_resume(resume)
        assert repo.get_resume("missing") is None
        repo.save_resume_parsed("r1", {"name": "Ada"})
        save_sql, save_params = conn.statements[-1]
        assert "parse_status = 'parsed'" in save_sql
        assert save_params[0] == '{"name": "Ada"}'
        assert repo.delete_resume("r1", "u1") is True

    def test_version_insert_and_list(self):
        from app.schemas.resumes import ResumeVersion

        repo, conn = make_repo(("rc", 1), ("all", []))
        version = ResumeVersion(
            id="", user_id="u1", parent_resume_id="r1",
            version_label="v1", version_number=1,
            stored_filename="s.pdf", file_type="pdf",
        )
        assert repo.insert_resume_version(version)
        assert repo.list_resume_versions("r1") == []
        assert "status = 'active'" in conn.statements[-1][0]
        assert "ORDER BY version_number" in conn.statements[-1][0]

    def test_delete_user_data_single_transaction(self):
        opened = []

        def factory() -> FakeConnection:
            opened.append(True)
            return conn

        repo, conn = make_repo(*(("rc", 1),) * 12)
        repo._connect_factory = factory
        repo.delete_user_data("u1")
        assert len(opened) == 1  # atomic: one connection for all deletes
        tables = [sql.split("DELETE FROM ")[1].split(" ")[0] for sql, _ in conn.statements]
        assert tables == [
            "applications", "saved_opportunities", "resume_versions", "resumes",
            "notifications", "ai_usage_logs", "job_preferences",
            "application_preferences", "notification_preferences",
            "application_answer_profiles", "profiles", "admins",
        ]
        assert all(params == ("u1",) for _, params in conn.statements)

    def test_preferences_round_trip(self):
        from app.schemas.profiles import JobPreferences

        repo, conn = make_repo(("rc", 1), ("one", {"user_id": "u1", "target_roles": ["dev"]}))
        repo.upsert_job_preferences(JobPreferences(user_id="u1", target_roles=["dev"]))
        prefs = repo.get_job_preferences("u1")
        assert prefs is not None and prefs.target_roles == ["dev"]

    def test_list_profiles_limit_parameterized(self):
        repo, conn = make_repo(("all", []))
        repo.list_profiles(limit=25)
        assert conn.statements[0][1] == (25,)
        assert "LIMIT %s" in conn.statements[0][0]

    def test_no_string_interpolation_of_values(self):
        # Hostile values must travel as params, never inside SQL text.
        hostile = "u1' OR '1'='1"
        repo, conn = make_repo(("all", []), ("one", {"total": 0}), ("all", []))
        repo.list_saved(hostile)
        repo.list_opportunities(OpportunityFilters(cities=[hostile]), page=1, page_size=5)
        for sql, _params in conn.statements:
            assert hostile not in sql
        assert hostile in conn.statements[0][1]
        assert [hostile.lower()] in conn.statements[2][1]


class TestMigration0003Fallbacks:
    """Deployments without migration 0003 keep working with degradations."""

    def test_fts_falls_back_without_search_vector(self):
        from psycopg.errors import UndefinedColumn

        repo, conn = make_repo(
            UndefinedColumn("column search_vector does not exist"),
            ("one", {"total": 0}),
            ("all", []),
        )
        items, total = repo.list_opportunities(OpportunityFilters(q="python"), page=1, page_size=10)
        assert (items, total) == ([], 0)
        assert repo._use_search_vector is False
        retried_sql = conn.statements[-1][0]
        assert "search_vector" not in retried_sql
        assert "to_tsvector" in retried_sql
        assert "plainto_tsquery('english', %s)" in retried_sql

    def test_fts_fallback_is_cached(self):
        repo, conn = make_repo(("one", {"total": 0}), ("all", []))
        repo._use_search_vector = False
        repo.list_opportunities(OpportunityFilters(q="python"), page=1, page_size=10)
        for sql, _ in conn.statements:
            assert "search_vector" not in sql

    def test_sources_fall_back_without_health_columns(self):
        from psycopg.errors import UndefinedColumn

        base_row = {
            "id": "s1", "provider": "greenhouse", "source_key": "acme",
            "company": "Acme", "active": True, "last_synced": None,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        repo, conn = make_repo(
            UndefinedColumn("column last_sync_status does not exist"),
            ("all", [base_row]),
        )
        (source,) = repo.list_sources()
        assert repo._source_health_columns is False
        assert source.last_sync_status == "never"  # model default
        assert source.last_error == ""
        assert "last_sync_status" not in conn.statements[-1][0]

    def test_record_sync_degrades_to_last_synced_only(self):
        from psycopg.errors import UndefinedColumn

        repo, conn = make_repo(UndefinedColumn("no such column"), ("rc", 1))
        repo.record_source_sync("s1", success=True)
        assert repo._source_health_columns is False
        fallback_sql = conn.statements[-1][0]
        assert "last_synced" in fallback_sql
        assert "last_sync_status" not in fallback_sql

    def test_set_source_active_degrades(self):
        from psycopg.errors import UndefinedColumn

        repo, conn = make_repo(
            ("one", {"last_synced": None}),
            UndefinedColumn("no such column"),
            ("rc", 1),
        )
        assert repo.set_source_active("s1", False) is True
        fallback_sql = conn.statements[-1][0]
        assert fallback_sql.startswith("UPDATE opportunity_sources SET active = %s")

    def test_unrelated_errors_still_raise(self):
        from psycopg import OperationalError

        repo, _ = make_repo(OperationalError("down"))
        with pytest.raises(OperationalError):
            repo.list_sources()


class TestDatabaseErrorHandler:
    def test_db_errors_become_generic_500_without_leak(self):
        from fastapi.testclient import TestClient
        from psycopg import OperationalError

        from app.api import deps
        from app.main import create_app

        class ExplodingRepo:
            def ping(self):
                raise OperationalError("connect failed: password=hunter2-live-secret")

        app = create_app()
        app.dependency_overrides[deps.get_repository] = lambda: ExplodingRepo()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal Server Error"}
        assert "hunter2" not in resp.text
        assert "password" not in resp.text
