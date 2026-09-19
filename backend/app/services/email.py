"""Server-side email delivery via Resend.

All sending happens here; the Resend API key never leaves the backend.
When Resend is unconfigured the helpers no-op (returning ``sent=False``)
so local/dev flows keep working without spamming anyone.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger("careerpilot.email")

_RESEND_URL = "https://api.resend.com/emails"
_BRAND = "CareerPilot India"


def _client() -> httpx.Client:
    return httpx.Client(timeout=15)


def send_email(to: str, subject: str, text: str, html: str | None = None) -> dict:
    """Send one transactional email. Never raises: failures are logged."""
    settings = get_settings()
    if not settings.resend_api_key or not settings.resend_from_email or not to:
        return {"sent": False, "reason": "email-not-configured"}
    payload: dict = {
        "from": f"{_BRAND} <{settings.resend_from_email}>",
        "to": [to],
        "subject": f"[{_BRAND}] {subject}",
        "text": text,
    }
    if html:
        payload["html"] = html
    try:
        with _client() as client:
            resp = client.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            return {"sent": True, "id": resp.json().get("id", "")}
    except httpx.HTTPError as exc:
        log.warning("resend send failed: %r", exc)
        return {"sent": False, "reason": "provider-error"}


def send_job_alert(to: str, roles: list[str], job_count: int) -> dict:
    lines = "\n".join(f"- {role}" for role in roles[:10])
    return send_email(
        to,
        "New matching roles",
        f"{_BRAND} found {job_count} new role(s) matching your preferences:\n{lines}\n\n"
        "Open CareerPilot to review them.",
    )


def send_application_reminder(to: str, job_title: str, company: str) -> dict:
    return send_email(
        to,
        "Finish your application",
        f"You started an application for {job_title} at {company}. "
        "Did you complete it on the employer's site?\n\nOpen CareerPilot to confirm.",
    )


def send_enhancement_complete(to: str, version_label: str) -> dict:
    return send_email(
        to,
        "Resume enhancement ready",
        f"Your enhanced resume version '{version_label}' is ready for review in {_BRAND}.",
    )
