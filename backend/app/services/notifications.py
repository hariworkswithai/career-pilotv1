"""Server-side user notifications (feed records + optional email).

Notifications are created by backend events only. Email is sent only when the
user's notification preferences allow it; the feed record is always stored so
the in-app notifications page stays truthful.
"""

from __future__ import annotations

from app.db.base import Repository
from app.schemas.common import NotificationType
from app.schemas.operations import Notification
from app.services import email as email_service


def notify(
    repository: Repository,
    *,
    user_id: str,
    type: str,
    title: str,
    body: str = "",
    email: str | None = None,
    email_subject: str | None = None,
) -> str:
    """Store a feed notification and optionally email it per user prefs."""
    record = Notification(id="", user_id=user_id, type=type, title=title, body=body)
    notification_id = repository.insert_notification(record)
    if email and _email_allowed(type, repository.get_notification_preferences(user_id)):
        email_service.send_email(email, email_subject or title, f"{title}\n\n{body}".strip())
    return notification_id


def _email_allowed(type: str, prefs) -> bool:
    """User preference gate per notification type (default allow)."""
    if prefs is None:
        return True
    if type == NotificationType.MATCHING_JOB:
        return prefs.matching_jobs
    if type == NotificationType.APPLICATION_UPDATE:
        return prefs.application_updates
    if type == NotificationType.RESUME_SUGGESTION:
        return prefs.resume_suggestions
    return True
