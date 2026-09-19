"""Opportunity catalog endpoints (jobs & internships)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_repository
from app.api.rate_limits import rate_limit_ai, rate_limit_default
from app.core.security import VerifiedUser, current_user
from app.db.base import Repository
from app.schemas.common import EmploymentType, ExperienceLevel, WorkplaceType
from app.schemas.opportunities import (
    BatchMatchItem,
    BatchMatchRequest,
    MatchExplanation,
    MatchResult,
    OpportunityFilters,
    OpportunityList,
    OpportunityRecord,
    RecommendationItem,
    RecommendationList,
    SuggestionItem,
)
from app.services.explanations import explain_match_ai
from app.services.matching import compute_match, passes_hard_filters
from app.services.suggest import suggest_cities

router = APIRouter(tags=["opportunities"])


def _filters(
    q: str = "",
    q_roles: str = "",
    q_cities: str = "",
    work_modes: str = "",
    experience_levels: str = "",
    employment_types: str = "",
    min_salary: float | None = Query(default=None),
    posted_days: int | None = Query(default=None),
    sort: str = "relevance",
) -> OpportunityFilters:
    def _split(value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]

    work = []
    for w in _split(work_modes):
        try:
            work.append(WorkplaceType(w))
        except ValueError:
            continue
    levels = []
    for lv in _split(experience_levels):
        try:
            levels.append(ExperienceLevel(lv))
        except ValueError:
            continue
    types = []
    for et in _split(employment_types):
        try:
            types.append(EmploymentType(et))
        except ValueError:
            continue
    return OpportunityFilters(
        q=q,
        roles=_split(q_roles),
        cities=_split(q_cities),
        work_modes=work,
        experience_levels=levels,
        employment_types=types,
        min_salary=min_salary,
        posted_days=posted_days,
        sort=sort,
    )


@router.get("/jobs", response_model=OpportunityList)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    filters: OpportunityFilters = Depends(_filters),
    repository: Repository = Depends(get_repository),
) -> OpportunityList:
    items, total = repository.list_opportunities(filters, page, page_size)
    return OpportunityList(items=items, total=total, page=page, page_size=page_size)


@router.get("/internships", response_model=OpportunityList)
async def list_internships(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    filters: OpportunityFilters = Depends(_filters),
    repository: Repository = Depends(get_repository),
) -> OpportunityList:
    items, total = repository.list_opportunities(filters, page, page_size, internships_only=True)
    return OpportunityList(items=items, total=total, page=page, page_size=page_size)


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityRecord)
async def get_opportunity(
    opportunity_id: str,
    repository: Repository = Depends(get_repository),
) -> OpportunityRecord:
    record = repository.get_opportunity(opportunity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return record


@router.get("/suggest/cities", response_model=list[SuggestionItem])
async def suggest_city_names(
    q: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=8, ge=1, le=20),
    repository: Repository = Depends(get_repository),
) -> list[SuggestionItem]:
    """City autocomplete: canonical India cities plus catalog cities."""
    return suggest_cities(q, repository.list_cities(), limit)


@router.get("/opportunities/{opportunity_id}/match", response_model=MatchResult)
async def match_opportunity(
    opportunity_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> MatchResult:
    record = repository.get_opportunity(opportunity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    profile = repository.get_profile(user.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Complete your profile to see matches")
    prefs = repository.get_job_preferences(user.user_id)
    return compute_match(profile, record, prefs)


@router.post("/match-batch", response_model=list[BatchMatchItem], dependencies=[Depends(rate_limit_default)])
async def match_opportunities(
    request: BatchMatchRequest,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> list[BatchMatchItem]:
    """Score a list of opportunities against the user's profile in one call."""
    profile = repository.get_profile(user.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Complete your profile to see matches")
    prefs = repository.get_job_preferences(user.user_id)
    items: list[BatchMatchItem] = []
    for opp_id in dict.fromkeys(request.opportunity_ids[:100]):
        record = repository.get_opportunity(opp_id)
        if record:
            items.append(BatchMatchItem(opportunity_id=opp_id, match=compute_match(profile, record, prefs)))
    return items


def _profile_or_404(repository: Repository, user_id: str):
    from app.schemas.profiles import Profile

    profile: Profile | None = repository.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Complete your profile to see matches")
    return profile


@router.get("/recommendations", response_model=RecommendationList, dependencies=[Depends(rate_limit_default)])
async def list_recommendations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    internships_only: bool = Query(default=False),
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> RecommendationList:
    """Ranked recommendation feed: hard-filter eligibility, then deterministic
    match score, then freshness. Roles failing hard filters are excluded."""
    profile = _profile_or_404(repository, user.user_id)
    prefs = repository.get_job_preferences(user.user_id)

    ranked: list[RecommendationItem] = []
    seen = 0
    batch = 100
    while seen < 500:
        items, _ = repository.list_opportunities(
            OpportunityFilters(), page=seen // batch + 1, page_size=batch,
            internships_only=internships_only,
        )
        if not items:
            break
        for record in items:
            ok, _ = passes_hard_filters(profile, prefs, record)
            if not ok:
                continue
            ranked.append(
                RecommendationItem(
                    opportunity=record, match=compute_match(profile, record, prefs)
                )
            )
        seen += len(items)
        if len(items) < batch:
            break

    ranked.sort(
        key=lambda r: (r.match.score, r.opportunity.posted_at or r.opportunity.created_at),
        reverse=True,
    )
    total = len(ranked)
    start = (page - 1) * page_size
    return RecommendationList(items=ranked[start : start + page_size], total=total, page=page, page_size=page_size)


@router.post(
    "/opportunities/{opportunity_id}/match-explanation",
    response_model=MatchExplanation,
    dependencies=[Depends(rate_limit_ai)],
)
async def match_explanation(
    opportunity_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> MatchExplanation:
    """Deterministic score plus an AI-written explanation of that score.

    The model receives facts only and must not recalculate anything;
    repeat views are served from cache.
    """
    record = repository.get_opportunity(opportunity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    profile = _profile_or_404(repository, user.user_id)
    prefs = repository.get_job_preferences(user.user_id)
    match = compute_match(profile, record, prefs)
    return await explain_match_ai(
        repository, user_id=user.user_id, opportunity=record, match=match
    )
