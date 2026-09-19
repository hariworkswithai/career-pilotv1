"""Shared FastAPI dependencies (backward-compatible re-export)."""

from __future__ import annotations

from app.db import get_repository
from app.db.base import Repository

__all__ = ["Repository", "get_repository"]
