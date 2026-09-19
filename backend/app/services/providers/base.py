"""Shared provider logic: title normalization, experience/employment inference."""

from __future__ import annotations

import html
import re
from abc import ABC, abstractmethod

from app.schemas.common import EmploymentType, ExperienceLevel
from app.schemas.opportunities import RawJob

_CASE_EDGES = re.compile(r"(\w)([A-Z])")
_WS = re.compile(r"\s+")

_INTERNSHIP_MARKERS = [
    "intern",
    "internship",
    "fresher internship",
    "student developer",
    "co-op",
]

_EXPERIENCE_HINTS = [
    (r"\b(?:fresher|graduate trainee|0\s*to\s*[0-9]|0-\d)\b", ExperienceLevel.FRESHER),
    (r"\b(?:entry.level|junior)\b", ExperienceLevel.ENTRY),
    (r"\b(?:mid.level|intermediate|[25]\s*(?:\+)?\s*years?)\b", ExperienceLevel.MID),
    (r"\b(?:senior|sr\.?|lead|staff|principal)\b", ExperienceLevel.SENIOR),
    (r"\b(?:manager|director|head of|principal)\b", ExperienceLevel.LEAD),
]

_EMPLOYMENT_HINTS = [
    (r"\binternship\b", EmploymentType.INTERNSHIP),
    (r"\bpart[- ]time\b", EmploymentType.PART_TIME),
    (r"\bcontract\b", EmploymentType.CONTRACT),
    (r"\btemporary\b", EmploymentType.TEMPORARY),
    (r"\bfull[- ]time\b", EmploymentType.FULL_TIME),
]

_IGNORED_TERMS = {"remote", "hybrid", "india", "bangalore", "bengaluru", "mumbai", "pune",
                  "chennai", "delhi", "ncr", "gurgaon", "gurugram", "noida", "hyderabad",
                  "full-time", "full time", "part-time", "part time", "on-site"}


def normalize_title(raw: str) -> str:
    """Lowercase, collapse spacing, strip location/employment padding words."""
    title_clean = html.unescape(raw or "")
    title_clean = _CASE_EDGES.sub(r"\1 \2", title_clean)
    tokens = [
        t
        for t in _WS.sub(" ", title_clean.lower()).split()
        if t not in _IGNORED_TERMS
    ]
    return " ".join(tokens).strip()


def infer_employment_type(raw: str | None, title: str) -> EmploymentType:
    combined = f"{raw or ''} {title}".lower()
    if any(m in combined for m in _INTERNSHIP_MARKERS):
        return EmploymentType.INTERNSHIP
    for pattern, etype in _EMPLOYMENT_HINTS:
        if re.search(pattern, combined):
            return etype
    return EmploymentType.FULL_TIME


def infer_experience_level(title: str, description: str | None = None) -> ExperienceLevel | None:
    """Best-effort level guess. Returns None when nothing matches (neutral axis)."""
    combined = f"{title} {description or ''}".lower()
    for pattern, level in _EXPERIENCE_HINTS:
        if re.search(pattern, combined):
            return level
    return None


def is_internship_title(title: str) -> bool:
    low = title.lower()
    return any(m in low for m in _INTERNSHIP_MARKERS)


class BaseProvider(ABC):
    """Adapter contract shared by all ATS ingestion sources."""

    name: str = "base"
    base_url: str = ""

    def __init__(self, source_keys: list[str]) -> None:
        self.source_keys = source_keys
        self.last_errors: list[str] = []

    @abstractmethod
    async def fetch_source(self, source_key: str) -> list[RawJob]:
        """Fetch and normalize every job from one source (board)."""

    async def fetch_all(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        for key in self.source_keys:
            try:
                jobs.extend(await self.fetch_source(key))
            except Exception as exc:  # noqa: BLE001 - ingestion must not kill the run
                self.last_errors.append(f"{self.name}/{key}: {exc!r}")
        return jobs
