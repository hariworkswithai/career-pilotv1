"""Opportunity (job/internship) schemas: normalized model, search, filters, match."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import (
    ApplyDestination,
    Eligibility,
    EmploymentType,
    ExperienceLevel,
    RemoteScope,
    WorkplaceType,
)


class NormalizedLocation(BaseModel):
    """Structured, India-first location parsed from provider text."""

    raw: str = ""
    city: str | None = None
    state: str | None = None
    country: str | None = None
    workplace_type: WorkplaceType = WorkplaceType.ON_SITE
    remote_scope: RemoteScope = RemoteScope.NONE


class NormalizedOpportunity(BaseModel):
    """Canonical opportunity record after ingestion normalization."""

    provider: str
    external_id: str
    source_key: str
    title: str
    normalized_title: str
    company_name: str
    location: NormalizedLocation
    description_html: str = ""
    description_text: str = ""
    requirements_html: str = ""
    skills: list[str] = Field(default_factory=list)
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    experience_level: ExperienceLevel | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_text: str | None = None
    posted_at: datetime | None = None
    external_url: str = ""
    apply_url: str = ""
    apply_method: ApplyDestination = ApplyDestination.CONTINUE
    india_eligible: Eligibility = Eligibility.AMBIGUOUS
    eligibility_reason: str = ""
    is_internship: bool = False
    published: bool = True


class OpportunityRecord(NormalizedOpportunity):
    """Opportunity stored in the database (adds internal identity)."""

    id: str
    dedup_fingerprint: str
    source_id: str | None = None
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class RawJob(BaseModel):
    """Provider-agnostic raw job shape produced by provider adapters."""

    provider: str
    external_id: str
    source_key: str
    title: str
    company_name: str
    location_text: str
    description_html: str = ""
    description_text: str = ""
    employment_type_raw: str | None = None
    workplace_type_raw: str | None = None
    is_remote: bool | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_text: str | None = None
    posted_at: datetime | None = None
    external_url: str = ""
    apply_url: str = ""
    extra: dict = Field(default_factory=dict)


class OpportunityFilters(BaseModel):
    """User-facing filters for the jobs/internships catalog."""

    q: str = ""
    roles: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    work_modes: list[WorkplaceType] = Field(default_factory=list)
    experience_levels: list[ExperienceLevel] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    min_salary: float | None = None
    posted_days: int | None = None
    sort: str = "relevance"


class OpportunityList(BaseModel):
    items: list[OpportunityRecord]
    total: int
    page: int
    page_size: int


class MatchBreakdown(BaseModel):
    skills: float = 0.0
    experience: float = 0.0
    role: float = 0.0
    location_work_mode: float = 0.0
    education: float = 0.0


class MatchResult(BaseModel):
    score: int = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    gap_skills: list[str] = Field(default_factory=list)
    breakdown: MatchBreakdown
    explanation: list[str] = Field(default_factory=list)


class BatchMatchItem(BaseModel):
    opportunity_id: str
    match: MatchResult


class BatchMatchRequest(BaseModel):
    opportunity_ids: list[str] = Field(min_length=1, max_length=100)


class RecommendationItem(BaseModel):
    opportunity: OpportunityRecord
    match: MatchResult
    filtered_out: bool = False
    filter_reason: str = ""


class RecommendationList(BaseModel):
    items: list[RecommendationItem]
    total: int
    page: int
    page_size: int


class MatchExplanation(BaseModel):
    opportunity_id: str
    score: int
    breakdown: MatchBreakdown
    matched_skills: list[str] = Field(default_factory=list)
    gap_skills: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    ai_summary: str = ""
    cached: bool = False


class SuggestionItem(BaseModel):
    type: str  # "title" | "role" | "skill" | "city"
    value: str
    label: str
    category: str
