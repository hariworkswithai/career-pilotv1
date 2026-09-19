"""End-to-end API tests through FastAPI TestClient."""

from __future__ import annotations

from app.api.deps import get_repository
from app.schemas.common import ApplicationStatus
from tests.helpers import client_with_user, make_profile


def test_repository_dependency_is_process_wide_singleton():
    assert get_repository() is get_repository()


class TestCatalog:
    def test_health(self):
        client = client_with_user()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_list_jobs_public(self, repository):
        client = client_with_user(repository)
        resp = client.get("/jobs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) <= 3

    def test_search_jobs(self, repository):
        client = client_with_user(repository)
        resp = client.get("/jobs", params={"q": "frontend"})
        items = resp.json()["items"]
        assert len(items) == 1
        assert "Frontend" in items[0]["title"]

    def test_internships_only(self, repository):
        client = client_with_user(repository)
        resp = client.get("/internships")
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["is_internship"] is True

    def test_single_opportunity(self, repository):
        client = client_with_user(repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        resp = client.get(f"/opportunities/{opp_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == opp_id

    def test_unknown_opportunity_404(self, repository):
        client = client_with_user(repository)
        assert client.get("/opportunities/missing").status_code == 404


class TestMatch:
    def test_match_requires_profile(self, repository):
        client = client_with_user(repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        resp = client.get(f"/opportunities/{opp_id}/match")
        assert resp.status_code == 404

    def test_match_returns_score(self, repository):
        repository.upsert_profile(make_profile())
        client = client_with_user(repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        resp = client.get(f"/opportunities/{opp_id}/match")
        assert resp.status_code == 200
        body = resp.json()
        assert 0 <= body["score"] <= 100


class TestProfile:
    def test_get_default_profile(self, repository):
        client = client_with_user(repository)
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-123"

    def test_update_profile_roundtrip(self, repository):
        client = client_with_user(repository)
        payload = make_profile().model_dump()
        payload["headline"] = "Backend Engineer"
        resp = client.put("/profile", json=payload)
        assert resp.status_code == 200
        assert resp.json()["headline"] == "Backend Engineer"
        assert client.get("/profile").json()["headline"] == "Backend Engineer"


class TestSaved:
    def test_saved_lifecycle(self, repository):
        client = client_with_user(repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        assert client.put(f"/saved/{opp_id}").status_code == 200
        saved = client.get("/saved").json()
        assert len(saved) == 1 and saved[0]["id"] == opp_id
        assert client.delete(f"/saved/{opp_id}").status_code == 200
        assert client.get("/saved").json() == []

    def test_save_unknown_404(self, repository):
        client = client_with_user(repository)
        assert client.put("/saved/nope").status_code == 404


class TestResumes:
    PDF_MINIMAL = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\ntrailer\n<<>>\n%%EOF"

    def test_upload_rejects_wrong_type(self, repository):
        client = client_with_user(repository)
        resp = client.post(
            "/resumes", files={"file": ("resume.txt", b"hello", "text/plain")}
        )
        assert resp.status_code == 415

    def test_upload_docx_parsed(self, repository):
        from tests.helpers import make_docx_bytes

        client = client_with_user(repository)
        resp = client.post(
            "/resumes",
            files={"file": ("resume.docx", make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["file_type"] == "docx"
        assert body["file_size"] > 0

    def test_upload_pdf_without_text_is_rejected(self, repository):
        # A valid-but-textless PDF documents the scanned-image failure path.
        client = client_with_user(repository)
        resp = client.post(
            "/resumes",
            files={"file": ("scanned.pdf", self.PDF_MINIMAL, "application/pdf")},
        )
        assert resp.status_code == 422

    def test_upload_too_large(self, repository, monkeypatch):
        from app.core.config import get_settings

        client = client_with_user(repository)
        monkeypatch.setattr(get_settings(), "resume_max_mb", 1)
        big = b"x" * (2 * 1024 * 1024)
        resp = client.post(
            "/resumes", files={"file": ("resume.pdf", big, "application/pdf")}
        )
        assert resp.status_code == 413

    def test_delete_own_resume(self, repository):
        from tests.helpers import make_docx_bytes

        client = client_with_user(repository)
        created = client.post(
            "/resumes",
            files={"file": ("resume.docx", make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        ).json()
        assert client.delete(f"/resumes/{created['id']}").status_code == 200
        assert client.get(f"/resumes/{created['id']}").status_code == 404


class TestApplications:
    def _create(self, client):
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        resp = client.post("/applications", json={"opportunity_id": opp_id})
        assert resp.status_code == 200
        return resp.json()

    def test_create_get_list(self, repository):
        client = client_with_user(repository)
        app_row = self._create(client)
        assert app_row["status"] == "saved"
        assert client.get(f"/applications/{app_row['id']}").status_code == 200
        assert len(client.get("/applications").json()) == 1

    def test_invalid_transition_conflict(self, repository):
        client = client_with_user(repository)
        app_row = self._create(client)
        resp = client.patch(
            f"/applications/{app_row['id']}",
            json={"status": ApplicationStatus.APPLIED.value},
        )
        assert resp.status_code == 409

    def test_valid_transition_applies(self, repository):
        client = client_with_user(repository)
        app_row = self._create(client)
        resp = client.patch(
            f"/applications/{app_row['id']}",
            json={"status": ApplicationStatus.PREPARED.value},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "prepared"

    def test_create_on_not_eligible_422(self, repository):
        from tests.helpers import make_opportunity

        repository.upsert_opportunity(
            make_opportunity(title="US Only", india_eligible="not_eligible", published=False), "fp-us"
        )
        client = client_with_user(repository)
        id_row = client.get("/jobs", params={"q": "US Only"}).json()
        assert id_row["total"] == 0  # non-eligible roles never surface

        hidden = next(o for o in repository._opportunities.values() if not o.published)
        resp = client.post("/applications", json={"opportunity_id": hidden.id})
        assert resp.status_code == 422


class TestNotifications:
    def test_feed_empty_then_read_all(self, repository):
        client = client_with_user(repository)
        assert client.get("/notifications").json() == []
