"""Lever postings API adapter.

Public endpoint: GET https://api.lever.co/v0/postings/{site}?mode=json
returns a JSON array of postings with {id, text, categories{location,
commitment, team, department}, country, description (HTML), descriptionPlain,
lists[], createdAt (epoch ms), hostedUrl, applyUrl, workplaceType}. No auth
required. The official apply URL is always preserved.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime

import httpx

from app.schemas.opportunities import RawJob
from app.services.providers.base import BaseProvider
from app.services.providers.registry import build_source_url


class LeverAdapter(BaseProvider):
    name = "lever"

    async def fetch_source(self, source_key: str) -> list[RawJob]:
        url = build_source_url("lever", source_key)
        client = getattr(self, "_client", None)
        if client is not None:
            resp = await client.get(url)
        else:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()
        entries = payload if isinstance(payload, list) else payload.get("postings", [])

        jobs: list[RawJob] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            categories = entry.get("categories") or {}
            location_text = str(
                categories.get("location") or entry.get("location") or ""
            )
            workplace = str(
                categories.get("workplaceType")
                or entry.get("workplaceType")
                or ""
            )
            is_remote = workplace.lower() == "remote" or "remote" in location_text.lower()
            description_html = entry.get("description") or ""
            description_text = entry.get("descriptionPlain") or self._text(description_html)
            created = entry.get("createdAt")
            jobs.append(
                RawJob(
                    provider=self.name,
                    external_id=str(entry.get("id") or ""),
                    source_key=source_key,
                    title=entry.get("text") or "",
                    company_name="",
                    location_text=location_text,
                    description_html=description_html,
                    description_text=description_text,
                    employment_type_raw=str(categories.get("commitment") or "") or None,
                    workplace_type_raw=workplace or None,
                    is_remote=is_remote,
                    posted_at=self._parse_date(created),
                    external_url=entry.get("hostedUrl") or "",
                    apply_url=entry.get("applyUrl") or entry.get("hostedUrl") or "",
                    extra={"lever": {"site": source_key}},
                )
            )
        return jobs

    @staticmethod
    def _text(description_html: str) -> str:
        if not description_html:
            return ""
        text = html.unescape(description_html)
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"</(p|li|h1|h2|h3|div)>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"[ \t]+", " ", text).strip()

    @staticmethod
    def _parse_date(value) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, OSError, OverflowError):
            return None
