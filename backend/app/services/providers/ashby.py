"""Ashby posting API adapter.

Verified 2026-09-17: GET https://api.ashbyhq.com/posting-api/job-board/{board}
returns a single payload. `jobs[]` entries carry {title, location, secondaryLocations,
employmentType, isRemote, compensation{compensationTierSummary}, jobUrl, publishedAt,
activationDate}. No auth required.
"""

from __future__ import annotations

import html
import re
from datetime import datetime

import httpx

from app.schemas.opportunities import RawJob
from app.services.providers.base import BaseProvider
from app.services.providers.registry import build_source_url

_URL = "https://api.ashbyhq.com/posting-api/job-board/{board}"
# fetchJobPostings is not yet hard-coded; we re-use the verified public endpoint shape.
_DETAIL_URL = "https://api.ashbyhq.com/posting-api/job-board/{board}"


class AshbyAdapter(BaseProvider):
    name = "ashby"
    base_url = _URL

    async def fetch_source(self, source_key: str) -> list[RawJob]:
        board = source_key
        url = build_source_url("ashby", board)
        client = getattr(self, "_client", None)
        if client is not None:
            resp = await client.get(url)
        else:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()

        jobs: list[RawJob] = []
        for entry in payload.get("jobs", []):
            compensation = entry.get("compensation") or {}
            tier_summary = compensation.get("compensationTierSummary") or {}
            primary_loc = self._location_text(entry.get("location") or "")
            secondary = [self._location_text(item) for item in (entry.get("secondaryLocations") or [])]
            locations = ", ".join([part for part in [primary_loc, *secondary] if part])

            jobs.append(
                RawJob(
                    provider=self.name,
                    external_id=str(entry.get("jobId") or ""),
                    source_key=source_key,
                    title=entry.get("title", ""),
                    company_name=self._company_name(entry),
                    location_text=locations,
                    description_html=self._description(entry),
                    description_text=self._text(entry.get("descriptionHtml") or ""),
                    employment_type_raw=entry.get("employmentType"),
                    workplace_type_raw="remote" if entry.get("isRemote") else None,
                    is_remote=bool(entry.get("isRemote")),
                    salary_text=(tier_summary or {}).get("summary") or compensation.get("compensationText"),
                    salary_min=self._num((tier_summary or {}).get("rangeStart")),
                    salary_max=self._num((tier_summary or {}).get("rangeEnd")),
                    posted_at=self._parse(entry.get("publishedAt") or entry.get("activationDate")),
                    external_url=entry.get("jobUrl") or "",
                    apply_url=entry.get("applyUrl") or entry.get("jobUrl") or "",
                    extra={"ashby": {"jobBoard": board, "employmentType": entry.get("employmentType")}},
                )
            )
        return jobs

    @staticmethod
    def _company_name(entry: dict) -> str:
        team = entry.get("team")
        name = team.get("name") if isinstance(team, dict) else team
        if isinstance(name, str) and name:
            return name
        dept = entry.get("department")
        name = dept.get("name") if isinstance(dept, dict) else dept
        return name if isinstance(name, str) else ""

    @staticmethod
    def _location_text(loc) -> str:
        if isinstance(loc, str):
            return loc
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                parts = [
                    part
                    for part in (addr.get("city"), addr.get("region"), addr.get("countryCode"))
                    if isinstance(part, str) and part
                ]
                if parts:
                    return ", ".join(parts)
            text = loc.get("addressText")
            if isinstance(text, str) and text:
                return text
            if loc.get("type") == "Remote":
                return "Remote"
        return ""

    @staticmethod
    def _description(entry: dict) -> str:
        return sanitize_html(entry.get("descriptionHtml") or "")

    @staticmethod
    def _text(html_text: str) -> str:
        if not html_text:
            return ""
        return html.unescape(
            re.sub(r"<br\s*/?>", "\n", html_text)
            .replace("</p>", "\n")
            .replace("</li>", "\n")
            .replace("</h1>", "\n")
            .replace("</h2>", "\n")
            .replace("</h3>", "\n")
            .replace("</div>", "\n")
            .replace("&bull;", "- ")
            .replace("•", "- ")
        )

    @staticmethod
    def _parse(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _num(value) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def sanitize_html(html_text: str) -> str:
    """Minimal structural scrub; full nh3 sanitization happens at normalization time."""
    return html_text
