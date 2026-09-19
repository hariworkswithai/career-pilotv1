"""Tests for the matching engine."""

from __future__ import annotations

from app.schemas.common import ExperienceLevel
from app.schemas.profiles import Profile
from app.services.matching import compute_match
from tests.helpers import make_opportunity, make_profile


class TestComputeMatch:
    def test_high_skill_overlap_scores_high(self):
        profile = make_profile(skills=["python", "sql", "react"])
        opp = make_opportunity(
            title="Software Engineer",
            skills=["python", "sql", "react"],
            level=ExperienceLevel.MID,
        )
        result = compute_match(profile, opp)
        assert result.score >= 60
        assert result.matched_skills

    def test_zero_for_non_india_eligible(self):
        profile = make_profile()
        opp = make_opportunity(india_eligible="not_eligible")
        result = compute_match(profile, opp)
        assert result.score == 0
        assert "not eligible" in " ".join(result.explanation).lower()

    def test_gap_skills_are_reported(self):
        profile = make_profile(skills=["python"])
        opp = make_opportunity(skills=["python", "kubernetes", "terraform"])
        result = compute_match(profile, opp)
        assert "kubernetes" in result.gap_skills

    def test_remote_always_locally_ok(self):
        profile = make_profile()
        profile.city = "Mumbai"
        opp = make_opportunity(remote=True, skills=["python"])
        result = compute_match(profile, opp)
        assert result.breakdown.location_work_mode == 0.9

    def test_score_bounds(self):
        profile = make_profile(skills=[])
        for level in ExperienceLevel:
            opp = make_opportunity(level=level, skills=["go"])
            result = compute_match(profile, opp)
            assert 0 <= result.score <= 100

    def test_internship_match_with_unknown_experience_is_neutral(self):
        profile = make_profile()
        profile.experience = []
        opp = make_opportunity(
            title="Intern",
            level=ExperienceLevel.FRESHER,
            is_internship=True,
        )
        result = compute_match(profile, opp)
        # Unknown experience is never assumed to be zero (neutral 0.5).
        assert result.breakdown.experience == 0.5


def test_profile_years():
    profile = Profile(user_id="u", experience=[{"role": "r", "company": "c", "start_year": 2022, "end_year": 2026}])
    assert profile.years_of_experience() == 4.0
