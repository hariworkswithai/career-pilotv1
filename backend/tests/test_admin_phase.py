"""Phase 4 tests: admin source management, roles, audit, support access."""

from __future__ import annotations

import httpx

from app.services import audit as audit_log
from tests.helpers import client_with_user, make_docx_bytes, make_profile


def admin_client(repository):
    repository.set_admin("user-123")
    return client_with_user(repository)


class TestAdminAuth:
    def test_non_admin_forbidden_everywhere(self, repository):
        client = client_with_user(repository)
        assert client.get("/admin/status").status_code == 403
        assert client.get("/admin/users").status_code == 403
        assert client.get("/admin/applications").status_code == 403
        assert client.get("/admin/audit-logs").status_code == 403
        assert client.get("/admin/sources").status_code == 403
        assert client.post("/admin/sources", json={"source_type": "greenhouse", "board_identifier": "x"}).status_code == 403

    def test_admin_status_extended(self, repository):
        client = admin_client(repository)
        body = client.get("/admin/status").json()
        assert body["service"] == "ok"
        assert {"active_jobs", "sources_total", "sources_active", "sources_failed"} <= set(body)


class TestSourceManagement:
    def test_create_source(self, repository):
        client = admin_client(repository)
        resp = client.post(
            "/admin/sources",
            json={"source_type": "greenhouse", "board_identifier": "myco", "company_name": "MyCo"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["source_type"] == "greenhouse"
        assert body["is_active"] is True
        logs = repository.list_audit_logs()
        assert any(log.action == audit_log.SOURCE_CREATE for log in logs)

    def test_create_rejects_unknown_type(self, repository):
        client = admin_client(repository)
        resp = client.post(
            "/admin/sources", json={"source_type": "linkedin", "board_identifier": "x"}
        )
        assert resp.status_code == 422

    def test_create_rejects_ssrf_identifier(self, repository):
        client = admin_client(repository)
        for bad in ["https://evil.example/board", "../x", "a/b", ""]:
            resp = client.post(
                "/admin/sources", json={"source_type": "lever", "board_identifier": bad}
            )
            assert resp.status_code == 422, bad

    def test_duplicate_registration_updates(self, repository):
        client = admin_client(repository)
        payload = {"source_type": "ashby", "board_identifier": "acme", "company_name": "Acme"}
        first = client.post("/admin/sources", json=payload).json()
        second = client.post("/admin/sources", json={**payload, "company_name": "Acme Inc"}).json()
        assert first["id"] == second["id"]
        assert second["company_name"] == "Acme Inc"
        assert len(client.get("/admin/sources").json()) == 1

    def test_disable_enable_audited(self, repository):
        client = admin_client(repository)
        source_id = client.post(
            "/admin/sources", json={"source_type": "lever", "board_identifier": "acme"}
        ).json()["id"]
        assert client.patch(f"/admin/sources/{source_id}", json={"is_active": False}).json()["is_active"] is False
        assert client.patch(f"/admin/sources/{source_id}", json={"is_active": True}).json()["is_active"] is True
        actions = [log.action for log in repository.list_audit_logs()]
        assert audit_log.SOURCE_DISABLE in actions
        assert audit_log.SOURCE_ENABLE in actions

    def test_test_connection_ok(self, repository, monkeypatch):
        from app.services.providers import lever as lever_module

        async def fake_fetch_source(self, source_key: str):
            return []

        monkeypatch.setattr(lever_module.LeverAdapter, "fetch_source", fake_fetch_source)
        client = admin_client(repository)
        source_id = client.post(
            "/admin/sources", json={"source_type": "lever", "board_identifier": "acme"}
        ).json()["id"]
        resp = client.post(f"/admin/sources/{source_id}/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True and body["jobs_found"] == 0

    def test_test_connection_failure_is_user_safe(self, repository, monkeypatch):
        from app.services.providers import lever as lever_module

        async def boom(self, source_key: str):
            raise httpx.ConnectError("dns down")

        monkeypatch.setattr(lever_module.LeverAdapter, "fetch_source", boom)
        client = admin_client(repository)
        source_id = client.post(
            "/admin/sources", json={"source_type": "lever", "board_identifier": "acme"}
        ).json()["id"]
        resp = client.post(f"/admin/sources/{source_id}/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert "couldn't connect" in body["message"]
        assert "dns down" not in body["message"]

    def test_trigger_disabled_source_conflicts(self, repository):
        client = admin_client(repository)
        source_id = client.post(
            "/admin/sources", json={"source_type": "lever", "board_identifier": "acme"}
        ).json()["id"]
        client.patch(f"/admin/sources/{source_id}", json={"is_active": False})
        assert client.post(f"/admin/sources/{source_id}/trigger").status_code == 409

    def test_trigger_ingests_and_audits(self, repository, monkeypatch):
        from app.services.providers import lever as lever_module

        async def empty(self, source_key: str):
            return []

        monkeypatch.setattr(lever_module.LeverAdapter, "fetch_source", empty)
        client = admin_client(repository)
        source_id = client.post(
            "/admin/sources", json={"source_type": "lever", "board_identifier": "acme"}
        ).json()["id"]
        resp = client.post(f"/admin/sources/{source_id}/trigger")
        assert resp.status_code == 200
        assert resp.json()["providers_run"] == ["lever"]
        actions = [log.action for log in repository.list_audit_logs()]
        assert audit_log.INGESTION_TRIGGER in actions
        assert repository.get_source(source_id).last_sync_status == "healthy"


class TestRoleManagement:
    def test_grant_and_revoke_role(self, repository):
        repository.upsert_profile(make_profile(user_id="other-1"))
        client = admin_client(repository)
        granted = client.post("/admin/users/other-1/role", json={"is_admin": True}).json()
        assert granted["is_admin"] is True
        assert repository.is_admin("other-1")
        revoked = client.post("/admin/users/other-1/role", json={"is_admin": False}).json()
        assert revoked["is_admin"] is False
        actions = [log.action for log in repository.list_audit_logs()]
        assert audit_log.USER_ROLE_CHANGE in actions

    def test_cannot_revoke_own_role(self, repository):
        client = admin_client(repository)
        assert client.post("/admin/users/user-123/role", json={"is_admin": False}).status_code == 409
        assert repository.is_admin("user-123")

    def test_users_overview_has_no_private_content(self, repository):
        repository.upsert_profile(make_profile())
        client = admin_client(repository)
        users = client.get("/admin/users").json()
        assert users and users[0]["user_id"] == "user-123"
        assert set(users[0]) == {
            "user_id", "full_name", "is_admin", "onboarding_completed",
            "applications", "resumes", "saved_jobs",
        }


class TestSupportAccess:
    def _upload(self, client):
        resp = client.post(
            "/resumes",
            files={"file": ("resume.docx", make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    def test_reason_mandatory(self, repository):
        client = admin_client(repository)
        resume_id = self._upload(client)
        assert client.post("/admin/support/resume-access", json={"resume_id": resume_id, "reason": "short"}).status_code == 422

    def test_access_audited_and_returns_file(self, repository):
        client = admin_client(repository)
        resume_id = self._upload(client)
        resp = client.post(
            "/admin/support/resume-access",
            json={"resume_id": resume_id, "reason": "User reported a parsing error on this file"},
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"PK")
        logs = repository.list_audit_logs()
        entry = next(log for log in logs if log.action == audit_log.RESUME_SUPPORT_ACCESS)
        assert entry.metadata["reason"].startswith("User reported")
        assert entry.metadata["access_type"] == "support_view"

    def test_non_admin_cannot_access(self, repository):
        client = client_with_user(repository)
        assert client.post(
            "/admin/support/resume-access", json={"resume_id": "x", "reason": "a" * 20}
        ).status_code == 403

    def test_users_cannot_read_audit_logs(self, repository):
        client = client_with_user(repository)
        assert client.get("/admin/audit-logs").status_code == 403
