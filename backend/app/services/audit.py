"""Server-side audit logging for administrative and sensitive actions.

Audit records are written by the backend only — never trust the browser to
report its own admin activity. Secrets, tokens and passwords must never be
placed in metadata.
"""

from __future__ import annotations

from fastapi import Request

from app.db.base import Repository
from app.schemas.operations import AuditLog

# Logged admin/user actions (stable strings; do not rename casually).
SOURCE_CREATE = "source.create"
SOURCE_UPDATE = "source.update"
SOURCE_ENABLE = "source.enable"
SOURCE_DISABLE = "source.disable"
SOURCE_TEST = "source.test"
INGESTION_TRIGGER = "ingestion.trigger"
USER_ROLE_CHANGE = "user.role_change"
USER_DELETE = "user.delete"
ACCOUNT_DELETE = "account.delete"
JOB_ARCHIVE = "job.archive"
JOB_FORCE_EXPIRE = "job.force_expire"
RESUME_SUPPORT_ACCESS = "resume.support_access"


def client_ip(request: Request | None) -> str:
    if request is None or request.client is None:
        return ""
    return request.client.host or ""


def user_agent(request: Request | None) -> str:
    if request is None:
        return ""
    return (request.headers.get("user-agent") or "")[:300]


def log_audit(
    repository: Repository,
    *,
    actor_user_id: str,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    metadata: dict | None = None,
    request: Request | None = None,
) -> str:
    """Persist an audit record. Returns the record id."""
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata=dict(metadata or {}),
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )
    return repository.insert_audit_log(log)
