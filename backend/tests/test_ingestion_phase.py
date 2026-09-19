"""Phase 2 tests: Lever adapter, ingestion robustness, freshness, skills, autocomplete, SSRF."""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from app.db import InMemoryRepository
from app.schemas.opportunities import OpportunityFilters, RawJob
from app.services.providers import LeverAdapter
from app.services.providers.pipeline import extract_skills, normalize_raw_job, run_ingestion
from app.services.providers.registry import (
    SUPPORTED_PROVIDERS,
    adapter_for,
    build_source_url,
)
from tests.helpers import client_with_user, make_opportunity


def _raw_job(**overrides) -> RawJob:
    base = {
        "provider": "test",
        "external_id": "1",
        "source_key": "myco",
        "title": "Senior Software Engineer",
        "company_name": "MyCo",
        "location_text": "Bengaluru, India",
        "description_html": "<p>Build the future</p>",
        "description_text": "Build the future",
        "is_remote": False,
    }
    base.update(overrides)
    return RawJob(**base)


def _mock_client(body, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestRegistry:
    def test_supported_providers(self):
        assert set(SUPPORTED_PROVIDERS) == {"greenhouse", "ashby", "lever"}

    def test_build_urls(self):
        assert build_source_url("greenhouse", "myco").startswith("https://boards-api.greenhouse.io/")
        assert build_source_url("ashby", "myco").startswith("https://api.ashbyhq.com/")
        assert build_source_url("lever", "myco") == "https://api.lever.co/v0/postings/myco?mode=json"

    def test_unknown_provider_rejected(self):
        with pytest.raises(ValueError):
            build_source_url("linkedin", "myco")

    def test_malicious_identifiers_rejected(self):
        for bad in ["https://evil.com/x", "../secret", "a/b", "", "x" * 65, "-lead", "a b"]:
            with pytest.raises(ValueError):
                build_source_url("greenhouse", bad)

    def test_adapter_factory(self):
        assert adapter_for("lever", ["a"]).name == "lever"
        assert adapter_for("Greenhouse", ["a"]).name == "greenhouse"
        with pytest.raises(ValueError):
            adapter_for("naukri", ["a"])


class TestLeverAdapter:
    @pytest.mark.asyncio
    async def test_lever_parses_postings(self):
        body = [
            {
                "id": "abc-1",
                "text": "Backend Engineer",
                "categories": {"location": "Bengaluru", "commitment": "Full-time"},
                "country": "IN",
                "description": "<p>Build APIs</p>",
                "descriptionPlain": "Build APIs with Python",
                "createdAt": 1756684800000,
                "hostedUrl": "https://jobs.lever.co/myco/abc-1",
                "applyUrl": "https://jobs.lever.co/myco/abc-1/apply",
                "workplaceType": "on-site",
            }
        ]
        adapter = LeverAdapter(["myco"])
        adapter._client = _mock_client(body)
        jobs = await adapter.fetch_source("myco")
        assert len(jobs) == 1
        assert jobs[0].external_id == "abc-1"
        assert jobs[0].apply_url == "https://jobs.lever.co/myco/abc-1/apply"
        assert jobs[0].location_text == "Bengaluru"

    @pytest.mark.asyncio
    async def test_lever_malformed_entries_skipped(self):
        adapter = LeverAdapter(["myco"])
        adapter._client = _mock_client([{"id": "ok", "text": "Dev"}, "junk", None])
        jobs = await adapter.fetch_source("myco")
        assert [j.external_id for j in jobs] == ["ok"]

    @pytest.mark.asyncio
    async def test_lever_http_failure_raises(self):
        adapter = LeverAdapter(["myco"])
        adapter._client = _mock_client({}, status=500)
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.fetch_source("myco")

    @pytest.mark.asyncio
    async def test_lever_invalid_identifier_rejected_before_network(self):
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            return httpx.Response(200, json=[])

        adapter = LeverAdapter(["https://evil.example/"])
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(ValueError):
            await adapter.fetch_source("https://evil.example/")
        assert requested == []

    def test_lever_normalizes_to_canonical(self):
        raw = _raw_job(
            provider="lever",
            external_id="abc-1",
            title="Backend Engineer",
            company_name="",
            location_text="Bengaluru",
            apply_url="https://jobs.lever.co/myco/abc-1/apply",
        )
        norm = normalize_raw_job(raw)
        assert norm.apply_url == "https://jobs.lever.co/myco/abc-1/apply"


class TestIngestionRobustness:
    @pytest.mark.asyncio
    async def test_failing_provider_does_not_abort_others(self):
        repo = InMemoryRepository()

        class BadProvider:
            name = "test"
            last_errors: list[str] = []
            source_keys = ["x"]

            async def fetch_all(self):
                raise RuntimeError("provider down")

        class GoodProvider:
            name = "test"
            last_errors: list[str] = []
            source_keys = ["y"]

            async def fetch_all(self):
                return [_raw_job(title="Backend Engineer", external_id="b1")]

        result = await run_ingestion(repo, [BadProvider(), GoodProvider()])
        assert result.providers_run == ["test", "test"]
        assert result.inserted == 1
        assert result.errors  # failure recorded, other provider still ran

    @pytest.mark.asyncio
    async def test_failed_source_keeps_existing_jobs_active(self):
        repo = InMemoryRepository()

        class GoodProvider:
            name = "test"
            last_errors: list[str] = []
            source_keys = ["y"]

            async def fetch_all(self):
                return [_raw_job(title="Backend Engineer", external_id="b1")]

        class BadProvider:
            name = "test"  # same provider: outage on second run
            last_errors: list[str] = []
            source_keys = ["y"]

            async def fetch_all(self):
                raise RuntimeError("outage")

        await run_ingestion(repo, [GoodProvider()])
        result = await run_ingestion(repo, [BadProvider()])
        assert result.errors
        assert result.stale_marked == 0
        items, total = repo.list_opportunities(OpportunityFilters(), 1, 20)
        assert total == 1
        assert items[0].status == "active"

    @pytest.mark.asyncio
    async def test_missing_jobs_go_stale_only_after_success(self):
        repo = InMemoryRepository()

        class FullProvider:
            name = "test"
            last_errors: list[str] = []
            source_keys = ["y"]

            async def fetch_all(self):
                return [_raw_job(title="Backend Engineer", external_id="b1")]

        class EmptyProvider:
            name = "test"
            last_errors: list[str] = []
            source_keys = ["y"]

            async def fetch_all(self):
                return []

        await run_ingestion(repo, [FullProvider()])
        # Simulate the previous hourly run: the record predates this sync.
        rec = next(iter(repo._opportunities.values()))
        rec.updated_at = datetime.utcnow() - timedelta(hours=1)
        result = await run_ingestion(repo, [EmptyProvider()])
        assert result.stale_marked == 1
        items, total = repo.list_opportunities(OpportunityFilters(), 1, 20)
        assert total == 0  # stale hidden from normal search

    @pytest.mark.asyncio
    async def test_stale_jobs_expire_after_14_days(self):
        repo = InMemoryRepository()
        repo.upsert_opportunity(make_opportunity(), "fp-old")
        rec_id = next(iter(repo._opportunities))
        rec = repo._opportunities[rec_id]
        rec.status = "stale"
        rec.updated_at = datetime.utcnow() - timedelta(days=15)

        class EmptyProvider:
            name = "test"
            last_errors: list[str] = []
            source_keys = ["y"]

            async def fetch_all(self):
                return []

        result = await run_ingestion(repo, [EmptyProvider()])
        assert result.expired_marked == 1
        assert repo._opportunities[rec_id].status == "expired"

    @pytest.mark.asyncio
    async def test_ingestion_is_idempotent(self):
        repo = InMemoryRepository()

        class StableProvider:
            name = "test"
            last_errors: list[str] = []
            source_keys = ["y"]

            async def fetch_all(self):
                return [_raw_job(title="Backend Engineer", external_id="b1")]

        first = await run_ingestion(repo, [StableProvider()])
        second = await run_ingestion(repo, [StableProvider()])
        assert (first.inserted, first.updated) == (1, 0)
        assert (second.inserted, second.updated) == (0, 1)


class TestSkillExtraction:
    def test_aliases_normalized(self):
        skills = extract_skills("Frontend Dev", "We use JS, Postgres and powerbi daily")
        assert "javascript" in skills
        assert "postgresql" in skills
        assert "power bi" in skills
        assert "js" not in skills
        assert "postgres" not in skills

    def test_no_go_inside_django(self):
        assert extract_skills("Backend", "Deep Django experience") == ["django"]

    def test_backend_frontend_are_distinct_signals(self):
        assert "python" in extract_skills("Backend Engineer", "Python APIs")
        assert "python" not in extract_skills("Frontend Engineer", "React UI")


class TestCityAutocomplete:
    def test_alias_resolution(self, repository):
        client = client_with_user(repository)
        resp = client.get("/suggest/cities", params={"q": "bang"})
        assert resp.status_code == 200
        values = [item["value"] for item in resp.json()]
        assert "bengaluru" in values

    def test_bombay_resolves_to_mumbai(self, repository):
        client = client_with_user(repository)
        resp = client.get("/suggest/cities", params={"q": "bombay"})
        assert resp.status_code == 200
        assert resp.json()[0]["value"] == "mumbai"

    def test_unknown_query_returns_empty(self, repository):
        client = client_with_user(repository)
        assert client.get("/suggest/cities", params={"q": "zzznocity"}).json() == []

    def test_query_required(self, repository):
        client = client_with_user(repository)
        assert client.get("/suggest/cities").status_code == 422

    def test_unrelated_cities_not_merged(self, repository):
        client = client_with_user(repository)
        values = [i["value"] for i in client.get("/suggest/cities", params={"q": "mum"}).json()]
        assert "mumbai" in values
        assert "bengaluru" not in values
