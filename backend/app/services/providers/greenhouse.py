"""Greenhouse boards API adapter.

Verified 2026-09-17: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
is public, returns `jobs[]` with {title, location{name}, content, absolute_url,
updated_at, internal_job_id, metadata, ...}. Detail per job (`?questions=true`) is
fetched lazily and is not needed for normal ingestion.
"""

from __future__ import annotations

import html
from datetime import datetime

import httpx

from app.schemas.opportunities import RawJob
from app.services.providers.base import BaseProvider
from app.services.providers.registry import build_source_url

_BOARDS_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseAdapter(BaseProvider):
    name = "greenhouse"
    base_url = _BOARDS_URL

    async def fetch_source(self, source_key: str) -> list[RawJob]:
        dev_mode = source_key.startswith("dev:")
        token = source_key.split(":", 1)[1] if dev_mode else source_key
        url = build_source_url("greenhouse", token)
        client = getattr(self, "_client", None)
        if client is not None:
            resp = await client.get(url)
        else:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()

        jobs: list[RawJob] = []
        for entry in payload.get("jobs", []):
            loc = entry.get("location", {}) or {}
            content = html.unescape(entry.get("content", "") or "")
            is_remote = (
                "remote" in (loc.get("name") or "").lower()
                or (entry.get("is_confidential") is False and "remote" in content[:2000].lower())
            )
            jobs.append(
                RawJob(
                    provider=self.name,
                    external_id=str(entry.get("internal_job_id") or ""),
                    source_key=source_key,
                    title=entry.get("title", ""),
                    company_name=entry.get("employer_name") or (loc.get("employer") or ""),
                    location_text=loc.get("name") or "",
                    description_html=content,
                    description_text=self._text(content),
                    employment_type_raw=self._extract_field(entry, "employment_type"),
                    workplace_type_raw=self._extract_field(entry, "workplace-type"),
                    is_remote=is_remote,
                    salary_text=self._extract_compensation(entry),
                    posted_at=self._parse_date(entry.get("updated_at")),
                    external_url=entry.get("absolute_url") or "",
                    apply_url=entry.get("absolute_url") or "",
                    extra={"greenhouse": {"id": entry.get("id", "")}},
                )
            )
        return jobs

    @staticmethod
    def _text(content_html: str) -> str:
        return (
            html.unescape(
                re_sub("&nbsp;", " ", content_html)
                .replace("<br>", "\n")
                .replace("<br/>", "\n")
                .replace("</p>", "\n")
                .replace("<li>", "\n- ")
            )
            if content_html
            else ""
        )

    @staticmethod
    def _extract_field(entry: dict, key: str) -> str | None:
        for meta in entry.get("metadata") or []:
            if (meta.get("name") or "").lower().replace("-", " ") == key.lower().replace("-", " "):
                value = meta.get("value") or meta.get("id")
                if isinstance(value, list):
                    return ", ".join(str(v) for v in value)
                return str(value) if value else None
        return None

    @staticmethod
    def _extract_compensation(entry: dict) -> str | None:
        candidates: list[str] = []
        for meta in entry.get("metadata") or []:
            name = (meta.get("name") or "").lower()
            value = meta.get("value")
            if value and ("compensation" in name or "salary" in name or "pay" in name):
                if isinstance(value, (dict, list)):
                    continue
                candidates.append(str(value))
        return " / ".join(candidates) if candidates else None

    @staticmethod
    def _parse_date(value) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None


def re_sub(pattern: str, repl: str, text: str) -> str:
    """Shim to keep the module free of the `re` import at call sites."""
    import re

    return re.sub(pattern, repl, text, flags=re.IGNORECASE)
