"""Deterministic matching engine.

Phase-3 contract — HARD FILTERS + DETERMINISTIC SCORE + OPTIONAL AI EXPLANATION:

- AI never calculates the score. Weights are fixed here (never scattered):
  skills 40% / experience 25% / role-title 15% / location-work-mode 12% /
  education 8%.
- Documented neutral strategies (no invented user data):
  - user has no skills while the job lists skills -> skills score 0
    (missing information is reported, never faked);
  - job lists no identifiable skills -> neutral 0.5;
  - user experience unknown -> neutral 0.5 (never assumed zero);
  - job states no experience level -> full 1.0;
  - education -> soft factor only (0.5 base, see _education_score).
- Skill identity is phrase-subset based: profile "react" does NOT cover job
  "react native" (all tokens of the required phrase must be present), while
  profile "react native" does cover job "react".
- Generic title words (engineer/developer/...) alone can never yield a high
  role score.
"""

from __future__ import annotations

import re

from app.schemas.common import Eligibility, EmploymentType, ExperienceLevel, WorkMode, WorkplaceType
from app.schemas.opportunities import MatchBreakdown, MatchResult, OpportunityRecord
from app.schemas.profiles import JobPreferences, Profile

SKILL_WEIGHT = 0.40
EXPERIENCE_WEIGHT = 0.25
ROLE_WEIGHT = 0.15
LOCATION_WORK_MODE_WEIGHT = 0.12
EDUCATION_WEIGHT = 0.08

NEUTRAL = 0.5

_SKILL_WORDS = re.compile(r"[^a-z0-9+#.]+")

# Title words so generic they carry almost no role signal on their own.
_GENERIC_TITLE_WORDS = frozenset(
    {
        "engineer", "engineering", "developer", "development", "manager",
        "management", "executive", "associate", "staff", "senior", "sr",
        "junior", "jr", "lead", "trainee", "specialist", "consultant",
    }
)

# Abbreviation equivalence groups for role matching ("ML" == "machine
# learning"). Curated and minimal; unknown abbreviations never match.
_ROLE_ALIAS_GROUPS = frozenset(
    {
        frozenset({"ml", "machine", "learning"}),
        frozenset({"ai", "artificial", "intelligence"}),
        frozenset({"qa", "quality", "assurance"}),
    }
)


def _expand_aliases(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for group in _ROLE_ALIAS_GROUPS:
        if expanded & group:
            expanded |= group
    return expanded

# Degree level ranking for the soft education comparison.
_DEGREE_LEVELS = [
    (re.compile(r"\b(ph\.?d|doctorate)\b"), 4),
    (re.compile(r"\b(master|m\.?tech|m\.?sc|mba|m\.?com|post.?grad)\b"), 3),
    (re.compile(r"\b(bachelor|b\.?tech|b\.?e\.?|b\.?sc|b\.?com|bba|under.?grad|graduate)\b"), 2),
    (re.compile(r"\b(diploma|12th|hsc|intermediate)\b"), 1),
]


def _tokens(text: str) -> set[str]:
    return {t for t in _SKILL_WORDS.split(text.lower()) if len(t) >= 2}


def _phrase_tokens(skill: str) -> frozenset[str]:
    return frozenset(t for t in _SKILL_WORDS.split(skill.lower().strip()) if len(t) >= 2)


def _match_skills(profile: Profile, opp: OpportunityRecord) -> tuple[list[str], list[str]]:
    """Phrase-subset skill comparison. Returns (matched, gaps) display names."""
    profile_tokens: set[str] = set()
    for skill in profile.skills:
        profile_tokens |= set(_phrase_tokens(skill))
    matched: list[str] = []
    gaps: list[str] = []
    for skill in opp.skills:
        phrase = set(_phrase_tokens(skill))
        if not phrase:
            continue
        if phrase <= profile_tokens:
            matched.append(skill)
        else:
            gaps.append(skill)
    return matched, gaps


def _skills_score(profile: Profile, opp: OpportunityRecord) -> float:
    phrases = [s for s in opp.skills if _phrase_tokens(s)]
    if not phrases:
        # No identifiable job skills: neutral, never punishing the user.
        return NEUTRAL
    if not profile.skills:
        # Missing user information is reported, not faked.
        return 0.0
    matched, _ = _match_skills(profile, opp)
    return len(matched) / len(phrases)


def _experience_score(profile: Profile, opp: OpportunityRecord) -> float:
    if not profile.experience:
        # Unknown experience is never assumed to be zero.
        return NEUTRAL
    years = profile.years_of_experience()
    level = opp.experience_level
    if level is None:
        return 1.0
    expectations = {
        "fresher": (0, 1),
        "entry": (0, 2),
        "mid": (2, 5),
        "senior": (5, 9),
        "lead": (9, 99),
    }
    lo, hi = expectations.get(level.value, (0, 99))
    if years < lo:
        return max(0.0, 1.0 - (lo - years) / 3.0)
    if years > hi:
        return max(0.0, 1.0 - (years - hi) / 6.0)
    return 1.0


def _role_score(
    profile: Profile, opp: OpportunityRecord, prefs: JobPreferences | None = None
) -> float:
    targets = [profile.headline, *profile.skills]
    if prefs:
        targets.extend(prefs.target_roles)
    haystack = _expand_aliases(_tokens(" ".join(targets)) - _GENERIC_TITLE_WORDS)
    if not haystack:
        return 0.0
    job_tokens = _expand_aliases(_tokens(f"{opp.normalized_title} {opp.title}") - _GENERIC_TITLE_WORDS)
    if not job_tokens:
        # Job title carries no specific signal beyond generic words.
        return 0.0
    return len(job_tokens & haystack) / len(job_tokens)


def _location_work_mode_score(
    profile: Profile, opp: OpportunityRecord, prefs: JobPreferences | None = None
) -> float:
    is_remote = opp.location.workplace_type == WorkplaceType.REMOTE
    cities = [c.lower() for c in (prefs.preferred_cities if prefs else [])]
    anywhere = not cities or "anywhere" in cities
    if opp.location.city and opp.location.city.lower() in cities:
        return 1.0
    if is_remote and (anywhere or (prefs is not None and prefs.remote_ok)):
        return 0.9
    if (
        profile.state
        and opp.location.state
        and opp.location.state.lower() == profile.state.lower()
    ):
        return 0.85
    if not profile.city and not cities:
        return 0.6
    if opp.location.city and profile.city and opp.location.city.lower() == profile.city.lower():
        return 1.0
    return 0.4


def _degree_level(text: str) -> int:
    level = 0
    for pattern, rank in _DEGREE_LEVELS:
        if pattern.search(text.lower()):
            level = max(level, rank)
    return level


def _education_score(profile: Profile, opp: OpportunityRecord) -> float:
    """Soft factor only: never rejects on missing education alone."""
    job_text = f"{opp.title} {opp.description_text}"
    required = _degree_level(job_text)
    if required == 0:
        # No stated requirement: neutral-warm, identical for everyone.
        return 0.6
    if not profile.education:
        return 0.4
    user_level = max((_degree_level(f"{e.degree} {e.field}") for e in profile.education), default=0)
    if user_level >= required:
        return 1.0
    if user_level > 0:
        return 0.6
    return 0.4


def passes_hard_filters(
    profile: Profile, prefs: JobPreferences | None, opp: OpportunityRecord
) -> tuple[bool, str]:
    """Eligibility gates evaluated before scoring. Failure excludes the role
    from normal recommendations (it is never silently demoted)."""
    if opp.india_eligible == Eligibility.NOT_ELIGIBLE:
        return False, "not eligible for India"
    if prefs is None:
        return True, ""
    # Job vs internship preference.
    if prefs.employment_types:
        wants_intern = EmploymentType.INTERNSHIP in prefs.employment_types
        wants_job = any(
            t in (EmploymentType.FULL_TIME, EmploymentType.CONTRACT, EmploymentType.PART_TIME)
            for t in prefs.employment_types
        )
        if opp.is_internship and not wants_intern:
            return False, "internship excluded by preference"
        if not opp.is_internship and not wants_job and wants_intern:
            return False, "only internships preferred"
    # Strict work-mode preference (ANY means no restriction).
    modes = [m for m in prefs.work_modes if m != WorkMode.ANY]
    if modes:
        want = {WorkMode.ON_SITE: WorkplaceType.ON_SITE, WorkMode.HYBRID: WorkplaceType.HYBRID,
                WorkMode.REMOTE: WorkplaceType.REMOTE}
        allowed = {want[m] for m in modes if m in want}
        if allowed and opp.location.workplace_type not in allowed:
            return False, "work mode excluded by preference"
    # Strict location preference ("anywhere" means no restriction).
    cities = [c.lower() for c in prefs.preferred_cities if c.strip()]
    if cities and "anywhere" not in cities:
        city_ok = bool(opp.location.city and opp.location.city.lower() in cities)
        state_ok = bool(
            opp.location.state
            and any(opp.location.state.lower() in c or c in opp.location.state.lower() for c in cities)
        )
        remote_ok = (
            opp.location.workplace_type == WorkplaceType.REMOTE
            and opp.india_eligible != Eligibility.NOT_ELIGIBLE
            and (prefs.remote_ok or WorkMode.REMOTE in prefs.work_modes)
        )
        if not (city_ok or state_ok or remote_ok):
            return False, "location excluded by preference"
    # Explicit experience-level preference acts as a strict gate when set.
    if prefs.experience_level is not None and opp.experience_level is not None:
        order = [ExperienceLevel.FRESHER, ExperienceLevel.ENTRY, ExperienceLevel.MID,
                 ExperienceLevel.SENIOR, ExperienceLevel.LEAD]
        try:
            if order.index(opp.experience_level) > order.index(prefs.experience_level) + 1:
                return False, "experience level above preference"
        except ValueError:
            pass
    return True, ""


def compute_match(profile: Profile, opp: OpportunityRecord, prefs: JobPreferences | None = None) -> MatchResult:
    """Compute the deterministic 0-100 match score. No external calls."""
    matched, gaps = _match_skills(profile, opp)

    skill_s = _skills_score(profile, opp)
    exp_s = _experience_score(profile, opp)
    role_s = _role_score(profile, opp, prefs)
    loc_s = _location_work_mode_score(profile, opp, prefs)
    edu_s = _education_score(profile, opp)

    if opp.india_eligible == Eligibility.NOT_ELIGIBLE:
        return MatchResult(
            score=0,
            matched_skills=sorted(set(matched)),
            gap_skills=sorted(set(gaps)),
            breakdown=MatchBreakdown(),
            explanation=["Role is not eligible for India"],
        )

    score = (
        skill_s * SKILL_WEIGHT
        + exp_s * EXPERIENCE_WEIGHT
        + role_s * ROLE_WEIGHT
        + loc_s * LOCATION_WORK_MODE_WEIGHT
        + edu_s * EDUCATION_WEIGHT
    )
    total = max(0, min(100, int(round(score * 100))))

    breakdown = MatchBreakdown(
        skills=skill_s,
        experience=exp_s,
        role=role_s,
        location_work_mode=loc_s,
        education=edu_s,
    )
    reasons = explain_match(skill_s, exp_s, role_s, loc_s, edu_s)
    return MatchResult(
        score=total,
        matched_skills=sorted(set(matched))[:12],
        gap_skills=sorted(set(gaps))[:12],
        breakdown=breakdown,
        explanation=reasons,
    )


def explain_match(skill_s: float, exp_s: float, role_s: float, loc_s: float, edu_s: float) -> list[str]:
    out: list[str] = []
    if skill_s >= 0.6:
        out.append("Strong skill overlap with the role")
    elif skill_s >= 0.3:
        out.append("Partial skill overlap; consider upskilling in flagged gaps")
    else:
        out.append("Low stated skill overlap with this role")
    if exp_s >= 0.8:
        out.append("Experience level looks aligned")
    else:
        out.append("Experience level may not match the role's expectation")
    if role_s >= 0.5:
        out.append("Role matches your headline/profile focus")
    if loc_s >= 0.8:
        out.append("Location/preference is compatible")
    if edu_s >= 0.8:
        out.append("Education background is compatible")
    return out
