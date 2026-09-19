"""Persistence layer.

A repository interface keeps business logic independent of the storage backend:
- `InMemoryRepository` is used in development/tests (no credentials required).
- `PostgresRepository` talks to Supabase PostgreSQL in production via direct
  psycopg connections (server-only `DATABASE_URL`, fallback `POSTGRES_DSN`).
  Every user-owned access is additionally enforced by RLS-compatible ownership
  filters in each query.
"""

from __future__ import annotations

import logging

from app.db.base import Repository
from app.db.inmemory import InMemoryRepository
from app.db.postgres import PostgresRepository

log = logging.getLogger(__name__)


def build_repository() -> InMemoryRepository | PostgresRepository:
    """Return the configured repository.

    Local development defaults to the in-memory repository so the app runs with zero
    credentials. Production sets `repository_backend=postgres` together with a
    server-only connection string (`DATABASE_URL`, fallback `POSTGRES_DSN`).
    """
    from app.core.config import get_settings

    settings = get_settings()
    if settings.repository_backend == "postgres":
        if settings.has_postgres_dsn:
            return PostgresRepository(settings)
        if settings.environment == "production":
            raise RuntimeError(
                "repository_backend=postgres but neither DATABASE_URL nor POSTGRES_DSN is set. "
                "Refusing to silently fall back to in-memory in production."
            )
        log.warning(
            "repository_backend=postgres but neither DATABASE_URL nor POSTGRES_DSN is set; "
            "falling back to the in-memory repository (development only)."
        )
    return InMemoryRepository()


_repository: Repository | None = None


def get_repository() -> Repository:
    """Process-wide (single-instance) repository dependency.

    Lives here (not in `app.api.deps`) so `core.security` can depend on it
    without a package import cycle. `app.api.deps.get_repository` re-exports
    this function for backward compatibility.
    """
    global _repository
    if _repository is None:
        _repository = build_repository()
    return _repository


__all__ = ["build_repository", "get_repository", "InMemoryRepository", "PostgresRepository"]
