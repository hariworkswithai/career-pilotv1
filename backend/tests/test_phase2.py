"""Phase 2 tests: auth/authz, onboarding, resume parsing/lifecycle, AI quota."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.resumes import ResumeParseResult
from tests.helpers import client_with_user, make_docx_bytes

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def upload_docx(client: TestClient) -> dict:
    resp = client.post(
        "/resumes",
        files={"file": ("resume.docx", make_docx_bytes(), DOCX_MIME)},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestAuthentication:
    def test_protected_route_requires_bearer(self, repository):
        app = create_app()
        from app.api import deps

        app.dependency_overrides[deps.get_repository] = lambda: repository
        client = TestClient(app)
        assert client.get("/profile").status_code == 401

    def test_unknown_opportunity_idor_not_leaked(self, repository):
        client = client_with_user(repository)
        assert client.get("/resumes/missing").status_code == 404


class TestAuthorization:
    def test_admin_endpoint_rejects_normal_user(self, repository):
        client = client_with_user(repository)
        assert client.get("/admin/status").status_code == 403

    def test_admin_endpoint_allows_admin(self, repository):
        repository.set_admin("user-123")
        client = client_with_user(repository)
        assert client.get("/admin/status").status_code == 200

    def test_admin_ai_usage_listing(self, repository):
        repository.set_admin("user-123")
        client = client_with_user(repository)
        assert client.get("/admin/ai-usage").status_code == 200


class TestOnboarding:
    def test_target_role_required(self, repository):
        client = client_with_user(repository)
        resp = client.post("/profile/onboarding", json={"full_name": "A", "target_roles": []})
        assert resp.status_code == 422

    def test_onboarding_writes_profile_and_prefs(self, repository):
        client = client_with_user(repository)
        resp = client.post(
            "/profile/onboarding",
            json={
                "full_name": "Priya",
                "city": "Bengaluru",
                "target_roles": ["Backend Engineer"],
                "employment_types": ["full_time"],
                "experience_level": "mid",
                "work_modes": ["hybrid"],
                "preferred_cities": ["Bengaluru", "Mumbai"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["onboarding_completed"] is True
        profile = client.get("/profile").json()
        assert profile["full_name"] == "Priya"
        assert profile["onboarding_completed"] is True
        prefs = client.get("/profile/job-preferences").json()
        assert prefs["target_roles"] == ["Backend Engineer"]
        assert prefs["employment_types"] == ["full_time"]

    def test_onboarding_remote_only_and_anywhere(self, repository):
        client = client_with_user(repository)
        resp = client.post(
            "/profile/onboarding",
            json={
                "target_roles": ["Frontend"],
                "remote_only": True,
                "anywhere_india": True,
                "work_modes": ["hybrid"],
            },
        )
        assert resp.status_code == 200
        prefs = client.get("/profile/job-preferences").json()
        assert prefs["work_modes"] == ["remote"]
        assert prefs["remote_ok"] is True
        assert prefs["preferred_cities"] == ["anywhere"]

    def test_onboarding_preserves_existing_profile_data(self, repository):
        from tests.helpers import make_profile

        repository.upsert_profile(make_profile())  # user-123 has skills/education already
        client = client_with_user(repository)
        resp = client.post(
            "/profile/onboarding",
            json={"full_name": "Priya Updated", "target_roles": ["Data Engineer"]},
        )
        assert resp.status_code == 200
        profile = client.get("/profile").json()
        assert profile["full_name"] == "Priya Updated"
        assert profile["skills"] == ["python", "sql", "react"]  # resume data kept


class TestResumeParsing:
    def test_parse_returns_validated_schema(self, repository):
        client = client_with_user(repository)
        created = upload_docx(client)
        resp = client.post(f"/resumes/{created['id']}/parse")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        parsed = ResumeParseResult.model_validate(body)
        assert isinstance(parsed.skills, list)
        assert parsed.name in ("Test Candidate", "")

    def test_schema_rejects_invented_fields(self):
        with __import__("pytest").raises(Exception):
            ResumeParseResult.model_validate(
                {
                    "name": "x",
                    "email": 123,  # invalid type must fail validation
                    "skills": {},
                }
            )

    def test_parse_failure_returns_user_safe_error(self, repository, monkeypatch):
        class BrokenProvider:
            async def parse_resume(self, text):  # type: ignore[no-untyped-def]
                raise ValueError("provider down")

        monkeypatch.setattr(
            "app.api.routes.resumes.get_ai_provider", lambda: BrokenProvider()
        )
        client = client_with_user(repository)
        created = upload_docx(client)
        resp = client.post(f"/resumes/{created['id']}/parse")
        assert resp.status_code == 422
        assert "couldn't read this file" in resp.json()["detail"].lower()


class TestEnhancementLifecycle:
    def _upload(self, client):
        return upload_docx(client)

    def test_enhance_returns_draft_without_version(self, repository):
        client = client_with_user(repository)
        created = self._upload(client)
        resp = client.post(f"/resumes/{created['id']}/enhance", params={"target_role": "Backend Engineer"})
        assert resp.status_code == 200, resp.text
        draft = resp.json()
        assert draft["changes"], "draft should propose changes"
        assert draft["quota_remaining"] == 2  # 3-limit, one just used
        assert draft["quota_limit"] == 3
        assert draft["quota_used"] == 1
        assert client.get(f"/resumes/{created['id']}/versions").json() == []

    def test_original_resume_is_immutable(self, repository):
        client = client_with_user(repository)
        created = self._upload(client)
        before = client.get(f"/resumes/{created['id']}").json()

        draft = client.post(
            f"/resumes/{created['id']}/enhance", params={"target_role": "Backend Engineer"}
        ).json()
        client.post(
            f"/resumes/{created['id']}/versions",
            json={
                "version_label": "enhanced-1",
                "changes": draft["changes"],
            },
        ).raise_for_status()

        after = client.get(f"/resumes/{created['id']}").json()
        assert after["stored_filename"] == before["stored_filename"]
        assert after["original_filename"] == before["original_filename"]
        assert after["file_type"] == before["file_type"]

    def test_save_version_then_list(self, repository):
        client = client_with_user(repository)
        created = self._upload(client)
        draft = client.post(f"/resumes/{created['id']}/enhance").json()
        saved = client.post(
            f"/resumes/{created['id']}/versions",
            json={"changes": draft["changes"]},
        )
        assert saved.status_code == 200, saved.text
        version = saved.json()
        assert version["version_number"] == 1
        assert version["parent_resume_id"] == created["id"]
        versions = client.get(f"/resumes/{created['id']}/versions").json()
        assert len(versions) == 1 and versions[0]["id"] == version["id"]

    def test_enhancement_quota_limited(self, repository):
        client = client_with_user(repository)
        created = self._upload(client)
        for _ in range(3):
            resp = client.post(f"/resumes/{created['id']}/enhance")
            assert resp.status_code == 200
        resp = client.post(f"/resumes/{created['id']}/enhance")
        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()

    def test_tailoring_has_separate_quota(self, repository):
        client = client_with_user(repository)
        created = self._upload(client)
        for _ in range(3):
            resp = client.post(
                f"/resumes/{created['id']}/enhance",
                params={"target_opportunity_id": "opp-1", "target_role": "Backend"},
            )
            assert resp.status_code == 200
        # Enhancement quota is untouched by tailorings
        resp = client.post(f"/resumes/{created['id']}/enhance")
        assert resp.status_code == 200
        resp = client.post(
            f"/resumes/{created['id']}/enhance",
            params={"target_opportunity_id": "opp-1", "target_role": "Backend"},
        )
        assert resp.status_code == 429


class TestVersionPreservation:
    def _upload_with_version(self, client, repository):
        created = upload_docx(client)
        draft = client.post(f"/resumes/{created['id']}/enhance").json()
        version = client.post(
            f"/resumes/{created['id']}/versions", json={"changes": draft["changes"]}
        ).json()
        return created, version

    def test_version_used_by_application_is_preserved(self, repository):
        client = client_with_user(repository)
        created, version = self._upload_with_version(client, repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        client.post("/applications", json={"opportunity_id": opp_id, "resume_version_id": version["id"]}).raise_for_status()
        resp = client.delete(f"/resumes/{created['id']}/versions/{version['id']}")
        assert resp.status_code == 409
        assert client.get(f"/resumes/{created['id']}/versions").json()

    def test_unused_version_can_be_soft_deleted(self, repository):
        client = client_with_user(repository)
        created, version = self._upload_with_version(client, repository)
        resp = client.delete(f"/resumes/{created['id']}/versions/{version['id']}")
        assert resp.status_code == 200
        assert client.get(f"/resumes/{created['id']}/versions").json() == []


class TestAccountLifecycle:
    def _onboard(self, client):
        resp = client.post(
            "/profile/onboarding",
            json={"full_name": "Priya", "target_roles": ["Backend Engineer"]},
        )
        assert resp.status_code == 200

    def test_export_contains_user_data(self, repository):
        client = client_with_user(repository)
        self._onboard(client)
        upload_docx(client)
        resp = client.get("/account/export")
        assert resp.status_code == 200
        body = resp.json()
        assert body["profile"]["user_id"] == "user-123"
        assert body["profile"]["onboarding_completed"] is True
        assert len(body["resumes"]) == 1
        assert "resume_versions" in body
        assert "applications" in body

    def test_delete_account_removes_data(self, repository):
        client = client_with_user(repository)
        self._onboard(client)
        created = upload_docx(client)
        assert client.delete("/account").status_code == 200
        assert client.get(f"/resumes/{created['id']}").status_code == 404
        resume_list = client.get("/resumes").json()
        assert resume_list == []
        assert client.get("/profile").json()["onboarding_completed"] is False
        assert client.get("/profile").json()["full_name"] == ""
