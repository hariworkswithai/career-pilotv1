"""Tests for application state machine and notification flows."""

from __future__ import annotations

import pytest

from app.schemas.common import ApplicationStatus
from app.services.applications import allowed_next, can_transition


class TestTransitions:
    @pytest.mark.parametrize(
        "current,target,expected",
        [
            (ApplicationStatus.SAVED, ApplicationStatus.PREPARED, True),
            (ApplicationStatus.SAVED, ApplicationStatus.APPLIED, False),
            (ApplicationStatus.PREPARED, ApplicationStatus.APPLIED, True),
            (ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW, True),
            (ApplicationStatus.APPLIED, ApplicationStatus.PREPARED, False),
            (ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER, True),
            (ApplicationStatus.INTERVIEW, ApplicationStatus.APPLIED, False),
            (ApplicationStatus.REJECTED, ApplicationStatus.APPLIED, False),
            (ApplicationStatus.OFFER, ApplicationStatus.INTERVIEW, False),
            (ApplicationStatus.WITHDRAWN, ApplicationStatus.APPLIED, False),
        ],
    )
    def test_transitions(self, current, target, expected):
        assert can_transition(current, target) == expected

    def test_allowed_next_contains_valid_moves(self):
        assert ApplicationStatus.PREPARED in allowed_next(ApplicationStatus.SAVED)
        assert ApplicationStatus.SAVED not in allowed_next(ApplicationStatus.APPLIED)
