"""Resume and resume-version schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResumeBase(BaseModel):
    id: str
    user_id: str
    original_filename: str
    stored_filename: str
    file_type: str  # "pdf" | "docx"
    file_size: int
    parse_status: str = "pending"  # pending | parsed | failed
    parse_error: str | None = None
    parsed_data: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeDetail(ResumeBase):
    searchable_text: str = ""
    parsed: dict = Field(default_factory=dict)


class ResumeUploadResult(BaseModel):
    id: str
    filename: str
    stored_filename: str
    file_type: str
    file_size: int


class ResumeVersion(BaseModel):
    id: str
    user_id: str
    parent_resume_id: str
    target_opportunity_id: str | None = None
    version_label: str
    version_number: int
    stored_filename: str
    file_type: str
    status: str = "active"  # active | archived
    parsed_data: dict = Field(default_factory=dict)
    enhancement_metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChangeItem(BaseModel):
    section: str
    original: str
    enhanced: str
    reason: str


class EnhancementDraft(BaseModel):
    version_label: str
    target_opportunity_id: str | None = None
    changes: list[ChangeItem] = Field(default_factory=list)
    quota_used: int | None = None
    quota_limit: int | None = None
    quota_remaining: int | None = None


class AcceptanceDecision(BaseModel):
    """Per-section accept/reject against an enhancement draft."""

    version_label: str
    accepted: dict[str, bool] = Field(default_factory=dict)  # section -> accepted?


class AnalysisFinding(BaseModel):
    category: str
    status: str  # good | needs_improvement
    message: str
    suggestion: str = ""


class ResumeAnalysis(BaseModel):
    findings: list[AnalysisFinding]
    summary: str = ""
    overall: str = "needs_improvement"


class ResumeEducation(BaseModel):
    institution: str = ""
    degree: str | None = None
    field: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class ResumeExperience(BaseModel):
    company: str = ""
    title: str = ""
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    description: str | None = None


class ResumeProject(BaseModel):
    name: str = ""
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class ResumeParseResult(BaseModel):
    """Canonical structured resume produced by Gemini Flash parsing.

    Every field is validated against this schema; missing information is stored as
    ``null`` or an empty array. The AI is instructed to never invent content.
    """

    name: str = ""
    email: str | None = None
    phone: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    education: list[ResumeEducation] = Field(default_factory=list)
    experience: list[ResumeExperience] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(default_factory=list)


class ResumeVersionCreate(BaseModel):
    version_label: str = ""
    target_opportunity_id: str | None = None
    changes: list[ChangeItem] = Field(default_factory=list)
