"""Routes and application wiring."""

from app.api.deps import get_repository
from app.api.routes import router as api_router

__all__ = ["api_router", "get_repository"]
