"""Ingestion pipeline: raw provider jobs -> normalized catalog records."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.core.security.sanitize import sanitize_html
from app.db.base import Repository
from app.schemas.common import ApplyDestination, Eligibility, EmploymentType
from app.schemas.operations import SyncResult
from app.schemas.opportunities import NormalizedOpportunity, RawJob
from app.services.locations import determine_eligibility, location_from_text
from app.services.providers import BaseProvider
from app.services.providers.dedupe import fingerprint

# Jobs missing from a successful sync for this long are retired to `expired`.
# Applications keep referencing them; they only leave normal search results.
EXPIRED_AFTER = timedelta(days=14)

_INTERNSHIP_TITLES = ("intern", "internship", "trainee", "graduate trainee", "apprenticeship", "co-op")

_COMPANY_REDIRECT: dict[str, str] = {}


def normalize_raw_job(raw: RawJob) -> NormalizedOpportunity:
    """Normalize a provider job into the canonical catalog record."""
    from app.services.providers.base import (
        infer_employment_type,
        infer_experience_level,
        is_internship_title,
        normalize_title,
    )

    title = raw.title or "Untitled role"
    normalized_title = normalize_title(title)
    is_intern = is_internship_title(title) or any(
        m in normalized_title for m in _INTERNSHIP_TITLES
    )

    employment = infer_employment_type(raw.employment_type_raw, normalized_title)
    if is_intern:
        employment = EmploymentType.INTERNSHIP

    location = location_from_text(raw.location_text, raw.is_remote)
    eligibility, reason = determine_eligibility(location, raw.description_text)
    published = eligibility != Eligibility.NOT_ELIGIBLE

    description_html = sanitize_html(raw.description_html)
    description_text = raw.description_text or _plain(description_html)

    external_url = raw.external_url or raw.apply_url
    apply_destination = _apply_destination(raw)

    return NormalizedOpportunity(
        provider=raw.provider,
        external_id=raw.external_id,
        source_key=raw.source_key,
        title=title,
        normalized_title=normalized_title,
        company_name=_COMPANY_REDIRECT.get(raw.company_name.strip().lower(), raw.company_name.strip() or "Unknown"),
        location=location,
        description_html=description_html,
        description_text=description_text,
        requirements_html="",
        skills=extract_skills(normalized_title, description_text),
        employment_type=employment,
        experience_level=infer_experience_level(normalized_title, description_text),
        salary_min=raw.salary_min,
        salary_max=raw.salary_max,
        salary_currency=raw.salary_currency,
        salary_text=raw.salary_text,
        posted_at=raw.posted_at,
        external_url=external_url,
        apply_url=raw.apply_url or external_url,
        apply_method=apply_destination,
        india_eligible=eligibility,
        eligibility_reason=reason,
        is_internship=is_intern,
        published=published,
    )


def _apply_destination(raw: RawJob) -> ApplyDestination:
    """Partner boards with a matching tracked source route apply through CareerPilot."""
    partner_markers = ("greenhouse.io", "ashbyhq.com", "lever.co")
    url = (raw.apply_url or raw.external_url or "").lower()
    if any(m in url for m in partner_markers):
        return ApplyDestination.CAREERPILOT
    if url:
        return ApplyDestination.CONTINUE
    return ApplyDestination.CONTINUE


def _plain(desc_html: str) -> str:
    import re

    if not desc_html:
        return ""
    return re.sub(r"<[^>]+>", " ", desc_html).strip()


SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c", "c++", "golang", "go", "rust",
    "sql", "postgres", "mysql", "mongodb", "redis", "kafka", "aws", "azure", "gcp",
    "docker", "kubernetes", "terraform", "react", "vue", "angular", "nextjs", "node",
    "node.js", "django", "flask", "fastapi", "spring", "spring boot", "machine learning",
    "deep learning", "nlp", "llm", "data science", "data analysis", "pandas", "numpy",
    "power bi", "tableau", "excel", "figma", "ui/ux", "graphql", "rest api", "html",
    "css", "tailwind", "flutter", "kotlin", "swift", "android", "ios", "devops", "ci/cd",
    "git", "agile", "scrum", "communication", "leadership", "analytical",
]

# Unambiguous display-name aliases only. When in doubt, do not add an entry:
# over-normalization merges unrelated technologies.
_SKILL_ALIASES = {
    "java script": "javascript",
    "js": "javascript",
    "postgres": "postgresql",
    "postgress": "postgresql",
    "powerbi": "power bi",
    "power-bi": "power bi",
    "k8s": "kubernetes",
    "ci cd": "ci/cd",
    "rest": "rest api",
}

_SKILL_PATTERNS = {
    skill: re.compile(r"(?<!\w)" + re.escape(skill) + r"(?!\w)")
    for skill in dict.fromkeys([*SKILL_KEYWORDS, *_SKILL_ALIASES])
}


def extract_skills(title: str, description_text: str) -> list[str]:
    """Extract known skill keywords present in the role text.

    Deterministic and dependency-free by design: word-boundary matching avoids
    false positives such as ``go`` inside ``django``, and a small alias map
    normalizes obvious variations (``JS`` -> ``javascript``). New aliases must
    be unambiguous before being added here.
    """
    combined = f"{title} {description_text}".lower()
    found: list[str] = []
    for skill in _SKILL_PATTERNS:
        if _SKILL_PATTERNS[skill].search(combined) and skill not in found:
            found.append(skill)
    # Deduplicate after alias mapping ("js" + "javascript" -> one entry).
    return list(dict.fromkeys(_SKILL_ALIASES.get(skill, skill) for skill in found))


async def run_ingestion(repository: Repository, providers: list[BaseProvider]) -> SyncResult:
    """Ingest all configured sources and persist normalized records.

    Idempotent: repeated runs upsert by dedup fingerprint (no duplicates).
    A failing provider is recorded and skipped — remaining providers still run
    and existing jobs are never deleted. Freshness transitions (active -> stale
    -> expired) happen only for providers whose fetch succeeded; a provider
    outage must never mark its whole catalog stale.
    """
    started = datetime.utcnow()
    result = SyncResult(started_at=started, completed_at=started, providers_run=[], fetched=0,
                        inserted=0, updated=0, rejected=0, errors=[])

    for provider in providers:
        result.providers_run.append(provider.name)
        try:
            raw_jobs = await provider.fetch_all()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"{provider.name}: {exc!r}")
            continue

        result.errors.extend(getattr(provider, "last_errors", []))
        result.fetched += len(raw_jobs)

        for raw in raw_jobs:
            try:
                normalized = normalize_raw_job(raw)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{provider.name} normalize: {exc!r}")
                continue

            fp = fingerprint(raw, normalized)
            source_id = raw.extra.get("greenhouse", {}).get("id")
            opp_id, created = repository.upsert_opportunity(
                normalized, fp, str(source_id) if source_id is not None else None
            )
            if created:
                result.inserted += 1
            else:
                result.updated += 1
            if normalized.india_eligible == Eligibility.NOT_ELIGIBLE:
                result.rejected += 1

        # Successful sync only: retire listings that vanished from the feed.
        result.stale_marked += repository.mark_stale_before(provider.name, started)

    result.expired_marked += repository.mark_expired_before(datetime.utcnow() - EXPIRED_AFTER)
    result.completed_at = datetime.utcnow()
    return result
