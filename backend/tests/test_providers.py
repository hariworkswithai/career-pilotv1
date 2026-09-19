"""Tests for provider normalization, dedupe, and ingestion pipeline."""

from __future__ import annotations

import httpx
import pytest

from app.db import InMemoryRepository
from app.schemas.common import ApplyDestination, Eligibility, EmploymentType
from app.schemas.opportunities import RawJob
from app.services.providers import AshbyAdapter, GreenhouseAdapter
from app.services.providers.base import (
    infer_employment_type,
    is_internship_title,
)
from app.services.providers.dedupe import fingerprint
from app.services.providers.pipeline import normalize_raw_job, run_ingestion


def raw_job(**overrides) -> RawJob:
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


class TestNormalize:
    def test_basic(self):
        raw = raw_job()
        norm = normalize_raw_job(raw)
        assert norm.provider == "test"
        assert norm.india_eligible == Eligibility.ELIGIBLE
        assert norm.normalized_title == "senior software engineer"

    def test_remote_worldwide_ambiguous(self):
        norm = normalize_raw_job(raw_job(location_text="Remote", is_remote=True))
        assert norm.india_eligible == Eligibility.AMBIGUOUS
        assert norm.published is True

    def test_us_remote_not_eligible(self):
        norm = normalize_raw_job(raw_job(location_text="Remote - US", is_remote=True))
        assert norm.india_eligible == Eligibility.NOT_ELIGIBLE
        assert norm.published is False

    def test_html_sanitized(self):
        raw = raw_job(description_html="<p>hi</p><script>alert(1)</script><img src=x onerror=alert(1)>")
        norm = normalize_raw_job(raw)
        assert "script" not in norm.description_html
        assert "onerror" not in norm.description_html

    def test_internship_detected(self):
        norm = normalize_raw_job(raw_job(title="Data Science Intern", employment_type_raw="Internship"))
        assert norm.is_internship is True
        assert norm.employment_type == EmploymentType.INTERNSHIP

    def test_skill_extraction(self):
        raw = raw_job(description_text="We need python and aws experience with machine learning")
        norm = normalize_raw_job(raw)
        assert "python" in norm.skills
        assert "aws" in norm.skills

    def test_partner_apply_routes_through_careerpilot(self):
        norm = normalize_raw_job(raw_job(apply_url="https://boards.greenhouse.io/myco/jobs/1"))
        assert norm.apply_method == ApplyDestination.CAREERPILOT
        norm2 = normalize_raw_job(raw_job(apply_url="https://example.com/careers/job/2"))
        assert norm2.apply_method == ApplyDestination.CONTINUE


class TestDedupe:
    def test_same_fingerprint_for_same_role(self):
        r1 = normalize_raw_job(raw_job(title="Backend Engineer", location_text="Pune, India"))
        r2 = normalize_raw_job(raw_job(title="Backend Engineer", location_text="Pune, India"))
        assert fingerprint(raw_job(title="Backend Engineer", location_text="Pune, India"), r1) == \
            fingerprint(raw_job(title="Backend Engineer", location_text="Pune, India"), r2)

    def test_different_fingerprint_for_different_city(self):
        r1 = normalize_raw_job(raw_job(location_text="Bengaluru, India"))
        r2 = normalize_raw_job(raw_job(location_text="Pune, India"))
        assert fingerprint(raw_job(location_text="Bengaluru, India"), r1) != fingerprint(raw_job(location_text="Pune, India"), r2)


class TestInference:
    def test_employment_mapping(self):
        assert infer_employment_type(None, "Summer Intern") == EmploymentType.INTERNSHIP
        assert infer_employment_type("Part-time", "Receptionist") == EmploymentType.PART_TIME

    def test_is_internship(self):
        assert is_internship_title("Summer Intern - Engineering")
        assert not is_internship_title("Staff Engineer")


class TestProviderAdapters:
    @pytest.mark.asyncio
    async def test_greenhouse_parses_board(self):
        body = {
            "jobs": [
                {
                    "id": 9,
                    "internal_job_id": 12345,
                    "title": "Frontend Engineer",
                    "location": {"name": "Bengaluru, India"},
                    "content": "<p>Ship UI with React</p>",
                    "absolute_url": "https://boards.greenhouse.io/myco/jobs/12345",
                    "updated_at": "2026-09-01T10:00:00Z",
                    "metadata": [{"name": "Employment Type", "value": "Full-time"}],
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        adapter = GreenhouseAdapter(["myco"])
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        jobs = await adapter.fetch_source("myco")
        assert len(jobs) == 1
        assert jobs[0].title == "Frontend Engineer"
        assert jobs[0].location_text == "Bengaluru, India"
        assert jobs[0].extra["greenhouse"]["id"] == 9

    @pytest.mark.asyncio
    async def test_ashby_parses_board(self):
        body = {
            "jobs": [
                {
                    "jobId": "abc-123",
                    "title": "Data Analyst",
                    "location": "Mumbai, India",
                    "secondaryLocations": [],
                    "employmentType": "Full-time",
                    "isRemote": False,
                    "compensation": {"compensationTierSummary": {"summary": "INR 600,000 - 900,000"}},
                    "jobUrl": "https://jobs.ashbyhq.com/myco/abc-123",
                    "publishedAt": "2026-08-15T00:00:00Z",
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        adapter = AshbyAdapter(["myco"])
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        jobs = await adapter.fetch_source("myco")
        assert len(jobs) == 1
        assert jobs[0].external_id == "abc-123"
        assert jobs[0].salary_text.startswith("INR")

    @pytest.mark.asyncio
    async def test_ashby_handles_structured_locations_and_team(self):
        body = {
            "jobs": [
                {
                    "jobId": "def-456",
                    "title": "Product Designer",
                    "team": {"id": "t1", "name": "Core"},
                    "location": {
                        "type": "Address",
                        "address": {"city": "Mumbai", "region": "Maharashtra", "countryCode": "IN"},
                        "addressText": "Mumbai, Maharashtra, India",
                    },
                    "secondaryLocations": [{"type": "Remote"}],
                    "employmentType": "Full-time",
                    "isRemote": False,
                    "compensation": {"compensationTierSummary": {"summary": "INR 1,200,000 - 1,800,000"}},
                    "jobUrl": "https://jobs.ashbyhq.com/myco/def-456",
                    "publishedAt": "2026-08-15T00:00:00Z",
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        adapter = AshbyAdapter(["myco"])
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        jobs = await adapter.fetch_source("myco")
        assert jobs[0].company_name == "Core"
        assert jobs[0].location_text == "Mumbai, Maharashtra, IN, Remote"


class TestPipeline:
    @pytest.mark.asyncio
    async def test_run_ingestion_inserts(self):
        repo = InMemoryRepository()

        class FakeProvider:
            name = "fake"
            last_errors = []
            source_keys = ["a"]

            async def fetch_all(self):
                return [raw_job(title="Backend Engineer", external_id="b1")]

        result = await run_ingestion(repo, [FakeProvider()])
        assert result.providers_run == ["fake"]
        assert result.inserted == 1
        assert result.fetched == 1

    @pytest.mark.asyncio
    async def test_run_ingestion_dedupes(self):
        repo = InMemoryRepository()

        class FakeProvider:
            name = "fake"
            last_errors = []
            source_keys = ["a"]

            async def fetch_all(self):
                return [raw_job(title="Backend Engineer", external_id="b1")]

        provider = FakeProvider()
        first = await run_ingestion(repo, [provider])
        second = await run_ingestion(repo, [provider])
        assert first.inserted == 1
        assert second.updated >= 1
        assert second.inserted == 0

    @pytest.mark.asyncio
    async def test_run_ingestion_accepts_int_source_ids(self):
        repo = InMemoryRepository()

        class FakeProvider:
            name = "fake"
            last_errors = []
            source_keys = ["a"]

            async def fetch_all(self):
                raw = raw_job(title="Engineer", external_id="b1")
                raw.extra.setdefault("greenhouse", {})["id"] = 8092044
                return [raw]

        result = await run_ingestion(repo, [FakeProvider()])
        assert result.inserted == 1
        row = repo.get_opportunity(next(iter(repo._opportunities)))
        assert row is not None
        assert row.source_id == "8092044"
