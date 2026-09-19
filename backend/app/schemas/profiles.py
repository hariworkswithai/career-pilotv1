"""User profile, preferences and settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import EmploymentType, ExperienceLevel, WorkMode


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    field: str = ""
    start_year: int | None = None
    end_year: int | None = None


class ExperienceItem(BaseModel):
    role: str = ""
    company: str = ""
    start_year: int | None = None
    end_year: int | None = None
    current: bool = False
    description: str = ""


class ProjectItem(BaseModel):
    title: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    link: str = ""


class Profile(BaseModel):
    user_id: str = ""
    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    state: str = ""
    education: list[Education] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    resume_completeness: int = 0
    onboarding_completed: bool = False

    def years_of_experience(self) -> float:
        """Best-effort total experience in years from dated entries."""
        total = 0.0
        for exp in self.experience:
            end = exp.end_year if exp.end_year else 2026
            start = exp.start_year or end
            total += max(0, end - start)
        return total


class JobPreferences(BaseModel):
    user_id: str = ""
    target_roles: list[str] = Field(default_factory=list)
    preferred_cities: list[str] = Field(default_factory=list)
    preferred_states: list[str] = Field(default_factory=list)
    work_modes: list[WorkMode] = Field(default_factory=list)
    experience_level: ExperienceLevel | None = None
    employment_types: list[EmploymentType] = Field(default_factory=list)
    salary_min: float | None = None
    salary_max: float | None = None
    remote_ok: bool = False


class OnboardingRequest(BaseModel):
    """Initial onboarding survey.

    Target role is required. Resume-provided information (skills, education,
    experience) is never requested here again; only fields the user supplies are
    written, so existing profile data is preserved.
    """

    full_name: str = ""
    city: str = ""
    target_roles: list[str] = Field(default_factory=list, min_length=1)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    experience_level: ExperienceLevel | None = None
    work_modes: list[WorkMode] = Field(default_factory=list)
    preferred_cities: list[str] = Field(default_factory=list)
    anywhere_india: bool = False
    remote_only: bool = False


class OnboardingResult(BaseModel):
    profile: Profile
    job_preferences: JobPreferences
    onboarding_completed: bool = True


class ApplicationPreferences(BaseModel):
    user_id: str = ""
    default_resume_id: str | None = None
    default_application_profile_id: str | None = None
    autofill_enabled: bool = True
    confirm_before_submit: bool = True


class NotificationPreferences(BaseModel):
    user_id: str = ""
    matching_jobs: bool = True
    internships: bool = True
    application_updates: bool = True
    resume_suggestions: bool = True


class ApplicationAnswerProfile(BaseModel):
    """Grounded answer sources used for drafting applications."""

    user_id: str = ""
    name: str = ""
    email: EmailStr | None = None
    phone: str = ""
    work_experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    confirmed_fields: list[str] = Field(default_factory=list)
