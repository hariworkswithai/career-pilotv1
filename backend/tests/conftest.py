"""Shared test fixtures."""

from __future__ import annotations

import pytest

from app.db import InMemoryRepository
from tests.helpers import bearer, client_with_user, seed_repository


@pytest.fixture(autouse=True)
def _mock_ai_provider(monkeypatch):
    """Tests must never call a real AI provider (keys in .env would trigger network).

    The resumes router imports `get_ai_provider` into its own namespace, so it is
    patched at the call site; individual tests may override again with a stub.
    """
    from app.services.ai import MockAIProvider

    monkeypatch.setattr(
        "app.api.routes.resumes.get_ai_provider", lambda: MockAIProvider()
    )


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Rate-limit state is per-process; never leak it between tests."""
    from app.api.rate_limits import reset_limiters

    reset_limiters()
    yield
    reset_limiters()


@pytest.fixture
def repository() -> InMemoryRepository:
    return seed_repository(InMemoryRepository())


@pytest.fixture
def authed_client(repository):
    return client_with_user(repository)


@pytest.fixture
def headers():
    return bearer()
