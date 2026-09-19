"""Shared enums and generic schema helpers for CareerPilot."""

from __future__ import annotations

from enum import StrEnum


class WorkplaceType(StrEnum):
    ON_SITE = "on_site"
    HYBRID = "hybrid"
    REMOTE = "remote"


class RemoteScope(StrEnum):
    """Geographic scope of a remote role, used for India eligibility."""

    NONE = "none"  # not remote
    INDIA = "india"
    WORLDWIDE = "worldwide"
    US = "us"
    CANADA = "ca"
    UK = "uk"
    OTHER = "other"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"
    TEMPORARY = "temporary"


class ExperienceLevel(StrEnum):
    FRESHER = "fresher"
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


class Eligibility(StrEnum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    AMBIGUOUS = "ambiguous"


class ApplicationStatus(StrEnum):
    SAVED = "saved"
    PREPARED = "prepared"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"
    WITHDRAWN = "withdrawn"


class ApplyDestination(StrEnum):
    CAREERPILOT = "careerpilot"
    ATS = "ats"
    CONTINUE = "continue"


class NotificationType(StrEnum):
    MATCHING_JOB = "matching_job"
    SAVED_JOB_UPDATE = "saved_job_update"
    APPLICATION_UPDATE = "application_update"
    RESUME_SUGGESTION = "resume_suggestion"


class WorkMode(StrEnum):
    """User preference for work modes."""

    ON_SITE = "on_site"
    HYBRID = "hybrid"
    REMOTE = "remote"
    ANY = "any"
