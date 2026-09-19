"""Tests for the in-memory repository (dev substitute for Supabase)."""

from __future__ import annotations

from datetime import datetime

from app.db import InMemoryRepository
from app.schemas.operations import Application, Notification
from app.schemas.opportunities import OpportunityFilters
from app.schemas.resumes import ResumeBase
from tests.helpers import make_opportunity, make_profile


def seeded() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.upsert_opportunity(make_opportunity(title="Engineer A", skills=["python"]), "fp-a")
    repo.upsert_opportunity(make_opportunity(title="Engineer B", city="pune", skills=["go"]), "fp-b")
    repo.upsert_opportunity(
        make_opportunity(title="Intern", is_internship=True, skills=["excel"]), "fp-c"
    )
    return repo


class TestOpportunities:
    def test_upsert_new_then_update_by_fingerprint(self):
        repo = InMemoryRepository()
        id1, created = repo.upsert_opportunity(make_opportunity(title="Engineer"), "fp-x")
        id2, created_again = repo.upsert_opportunity(make_opportunity(title="Engineer"), "fp-x")
        assert created is True
        assert created_again is False
        assert id1 == id2

    def test_list_filters_and_pagination(self):
        repo = seeded()
        items, total = repo.list_opportunities(OpportunityFilters(q="engineer"), page=1, page_size=1)
        assert total == 2
        assert len(items) == 1

    def test_internships_only(self):
        repo = seeded()
        items, total = repo.list_opportunities(OpportunityFilters(), page=1, page_size=10, internships_only=True)
        assert total == 1
        assert items[0].is_internship is True

    def test_city_filter(self):
        repo = seeded()
        items, total = repo.list_opportunities(OpportunityFilters(cities=["pune"]), page=1, page_size=10)
        assert total == 1
        assert items[0].location.city == "pune"

    def test_mark_stale(self):
        repo = seeded()
        cutoff = datetime(2026, 12, 31)
        count = repo.mark_stale_before("test", cutoff)
        assert count == 3


class TestSaved:
    def test_saved_flow(self):
        repo = seeded()
        items, _ = repo.list_opportunities(OpportunityFilters(), 1, 1)
        opp_id = items[0].id
        repo.add_saved("u1", opp_id)
        assert repo.list_saved("u1") == [opp_id]
        repo.remove_saved("u1", opp_id)
        assert repo.list_saved("u1") == []


class TestOwnership:
    def test_delete_resume_only_owner(self):
        repo = InMemoryRepository()
        repo.insert_resume(
            ResumeBase(id="r1", user_id="u1", original_filename="a.pdf", stored_filename="a.pdf",
                       file_type="pdf", file_size=10)
        )
        assert repo.delete_resume("r1", "u2") is False
        assert repo.delete_resume("r1", "u1") is True

    def test_delete_application_only_owner(self):
        repo = InMemoryRepository()
        repo.insert_application(Application(id="a1", user_id="u1", opportunity_id="o1"))
        assert repo.delete_application("a1", "u2") is False
        assert repo.delete_application("a1", "u1") is True

    def test_mark_notification_only_owner(self):
        repo = InMemoryRepository()
        repo.insert_notification(Notification(id="n1", user_id="u1", type="matching_job", title="t"))
        assert repo.mark_notification_read("n1", "u2") is False
        assert repo.mark_notification_read("n1", "u1") is True


class TestProfileRoundTrip:
    def test_profile_defaults(self):
        repo = InMemoryRepository()
        assert repo.get_profile("u-unknown") is None
        repo.upsert_profile(make_profile(user_id="u1"))
        loaded = repo.get_profile("u1")
        assert loaded and loaded.full_name == "Test Candidate"
