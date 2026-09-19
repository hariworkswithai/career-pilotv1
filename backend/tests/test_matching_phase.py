"""Phase 3 tests: spec weights, hard filters, recommendations, AI explanation."""

from __future__ import annotations

from app.schemas.common import EmploymentType, ExperienceLevel, WorkMode
from app.schemas.profiles import JobPreferences
from app.services import explanations
from app.services.matching import (
    EDUCATION_WEIGHT,
    EXPERIENCE_WEIGHT,
    LOCATION_WORK_MODE_WEIGHT,
    ROLE_WEIGHT,
    SKILL_WEIGHT,
    compute_match,
    passes_hard_filters,
)
from tests.helpers import client_with_user, make_opportunity, make_profile


def _prefs(**overrides) -> JobPreferences:
    base = {
        "user_id": "user-123",
        "target_roles": ["Software Engineer"],
        "preferred_cities": [],
        "work_modes": [],
        "remote_ok": False,
    }
    base.update(overrides)
    return JobPreferences(**base)


class TestSpecWeights:
    def test_weights_sum_to_one(self):
        total = SKILL_WEIGHT + EXPERIENCE_WEIGHT + ROLE_WEIGHT + LOCATION_WORK_MODE_WEIGHT + EDUCATION_WEIGHT
        assert abs(total - 1.0) < 1e-9

    def test_spec_values(self):
        assert (SKILL_WEIGHT, EXPERIENCE_WEIGHT, ROLE_WEIGHT, LOCATION_WORK_MODE_WEIGHT, EDUCATION_WEIGHT) == (
            0.40, 0.25, 0.15, 0.12, 0.08,
        )

    def test_breakdown_keys(self):
        result = compute_match(make_profile(), make_opportunity())
        assert set(result.breakdown.model_dump()) == {
            "skills", "experience", "role", "location_work_mode", "education",
        }


class TestSkillIdentity:
    def test_react_does_not_cover_react_native(self):
        profile = make_profile(skills=["react"])
        opp = make_opportunity(skills=["React Native"])
        result = compute_match(profile, opp)
        assert "React Native" in result.gap_skills
        assert "React Native" not in result.matched_skills

    def test_react_native_covers_react(self):
        profile = make_profile(skills=["React Native"])
        opp = make_opportunity(skills=["react"])
        result = compute_match(profile, opp)
        assert "react" in result.matched_skills

    def test_case_insensitive_match(self):
        profile = make_profile(skills=["Python"])
        opp = make_opportunity(skills=["python"])
        assert "python" in compute_match(profile, opp).matched_skills

    def test_no_user_skills_reports_zero_not_fake(self):
        profile = make_profile()
        profile.skills = []
        opp = make_opportunity(skills=["python", "sql"])
        result = compute_match(profile, opp)
        assert result.breakdown.skills == 0.0

    def test_job_without_skills_is_neutral(self):
        profile = make_profile()
        profile.skills = []
        opp = make_opportunity(skills=[])
        assert compute_match(profile, opp).breakdown.skills == 0.5


class TestExperienceNeutrality:
    def test_unknown_experience_is_neutral(self):
        profile = make_profile()
        profile.experience = []
        opp = make_opportunity(level=ExperienceLevel.SENIOR)
        assert compute_match(profile, opp).breakdown.experience == 0.5

    def test_known_experience_compatible(self):
        profile = make_profile()  # 5 years
        opp = make_opportunity(level=ExperienceLevel.MID)
        assert compute_match(profile, opp).breakdown.experience == 1.0

    def test_junior_against_senior_role_scores_low(self):
        from app.schemas.profiles import ExperienceItem

        profile = make_profile()
        profile.experience = [
            ExperienceItem(role="r", company="c", start_year=2025, end_year=2026)
        ]
        opp = make_opportunity(level=ExperienceLevel.SENIOR)
        assert compute_match(profile, opp).breakdown.experience < 0.5


class TestRoleScore:
    def test_generic_words_alone_do_not_score_high(self):
        profile = make_profile()
        profile.headline = "Engineer"
        profile.skills = []
        opp = make_opportunity(title="Senior Frontend Engineer", skills=[])
        assert compute_match(profile, opp).breakdown.role < 0.5

    def test_target_role_drives_score(self):
        profile = make_profile()
        profile.headline = ""
        profile.skills = []
        prefs = _prefs(target_roles=["Machine Learning Engineer"])
        opp = make_opportunity(title="ML Engineer", skills=[])
        assert compute_match(profile, opp, prefs).breakdown.role >= 0.5

    def test_unrelated_role_scores_low(self):
        profile = make_profile()
        prefs = _prefs(target_roles=["Data Analyst"])
        opp = make_opportunity(title="Senior Frontend Engineer", skills=["javascript"])
        assert compute_match(profile, opp, prefs).breakdown.role < 0.5


class TestHardFilters:
    def test_india_ineligible_fails(self):
        ok, reason = passes_hard_filters(make_profile(), _prefs(), make_opportunity(india_eligible="not_eligible"))
        assert not ok and "India" in reason

    def test_strict_remote_only(self):
        prefs = _prefs(work_modes=[WorkMode.REMOTE], remote_ok=True)
        ok, _ = passes_hard_filters(make_profile(), prefs, make_opportunity(remote=True))
        assert ok
        ok, _ = passes_hard_filters(make_profile(), prefs, make_opportunity(remote=False))
        assert not ok

    def test_anywhere_india_passes_any_city(self):
        prefs = _prefs(preferred_cities=["anywhere"])
        ok, _ = passes_hard_filters(make_profile(), prefs, make_opportunity(city="kolkata"))
        assert ok

    def test_city_preference_enforced(self):
        prefs = _prefs(preferred_cities=["bengaluru"])
        ok, _ = passes_hard_filters(make_profile(), prefs, make_opportunity(city="bengaluru"))
        assert ok
        ok, reason = passes_hard_filters(make_profile(), prefs, make_opportunity(city="mumbai"))
        assert not ok and "location" in reason

    def test_internship_preference(self):
        prefs = _prefs(employment_types=[EmploymentType.INTERNSHIP])
        ok, _ = passes_hard_filters(
            make_profile(), prefs, make_opportunity(title="Intern", is_internship=True),
        )
        assert ok
        ok, _ = passes_hard_filters(make_profile(), prefs, make_opportunity(title="Engineer"))
        assert not ok

    def test_no_prefs_passes_everything_eligible(self):
        ok, _ = passes_hard_filters(make_profile(), None, make_opportunity())
        assert ok


class TestRecommendationsEndpoint:
    def test_ranked_and_paginated(self, repository):
        from tests.helpers import seed_repository  # noqa

        repository.upsert_profile(make_profile())
        client = client_with_user(repository)
        resp = client.get("/recommendations", params={"page": 1, "page_size": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2
        scores = [item["match"]["score"] for item in body["items"]]
        assert scores == sorted(scores, reverse=True)
        for item in body["items"]:
            assert item["filtered_out"] is False
            assert "opportunity" in item and "match" in item

    def test_hard_filtered_roles_excluded(self, repository):
        repository.upsert_profile(make_profile())
        repository.upsert_job_preferences(_prefs(preferred_cities=["bengaluru"]))
        client = client_with_user(repository)
        body = client.get("/recommendations").json()
        cities = {item["opportunity"]["location"]["city"] for item in body["items"]}
        assert cities <= {"bengaluru"}

    def test_requires_profile(self, repository):
        client = client_with_user(repository)
        assert client.get("/recommendations").status_code == 404

    def test_pagination_bounds(self, repository):
        repository.upsert_profile(make_profile())
        client = client_with_user(repository)
        body = client.get("/recommendations", params={"page": 99, "page_size": 10}).json()
        assert body["items"] == [] and body["page"] == 99


class TestMatchExplanationEndpoint:
    def test_explanation_preserves_deterministic_score(self, repository):
        repository.upsert_profile(make_profile())
        client = client_with_user(repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        expected = client.get(f"/opportunities/{opp_id}/match").json()["score"]
        resp = client.post(f"/opportunities/{opp_id}/match-explanation")
        assert resp.status_code == 200
        body = resp.json()
        assert body["score"] == expected
        assert body["cached"] is False
        assert isinstance(body["ai_summary"], str)

    def test_second_call_served_from_cache(self, repository):
        repository.upsert_profile(make_profile())
        client = client_with_user(repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        client.post(f"/opportunities/{opp_id}/match-explanation")
        body = client.post(f"/opportunities/{opp_id}/match-explanation").json()
        assert body["cached"] is True

    def test_usage_logged(self, repository):
        repository.upsert_profile(make_profile())
        client = client_with_user(repository)
        opp_id = client.get("/jobs").json()["items"][0]["id"]
        client.post(f"/opportunities/{opp_id}/match-explanation")
        logs = repository.list_ai_usage("user-123")
        assert any(log.feature == "match_explanation" for log in logs)

    def test_missing_opportunity_404(self, repository):
        repository.upsert_profile(make_profile())
        client = client_with_user(repository)
        assert client.post("/opportunities/nope/match-explanation").status_code == 404

    def teardown_method(self):
        explanations.clear_explanation_cache()
