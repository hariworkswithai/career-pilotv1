"""Application lifecycle rules."""

from __future__ import annotations

from app.schemas.common import ApplicationStatus

_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.SAVED: {
        ApplicationStatus.PREPARED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.PREPARED: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.SAVED,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.OFFER,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.REJECTED,
        ApplicationStatus.OFFER,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.OFFER: {
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.WITHDRAWN: set(),
}


def can_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return target in _TRANSITIONS.get(current, set())


def allowed_next(current: ApplicationStatus) -> list[ApplicationStatus]:
    return sorted(_TRANSITIONS.get(current, set()), key=lambda s: s.value)
