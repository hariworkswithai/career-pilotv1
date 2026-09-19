"""FastAPI application entry point."""

from __future__ import annotations

import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)


async def _database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak raw database errors (which may contain SQL or connection
    details) to API consumers. Full traceback goes to server logs / Sentry."""
    logging.error("Database operation failed for %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CareerPilot India API", version="0.1.0")

    try:
        import sentry_sdk

        if settings.sentry_dsn:
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=0.1,
                send_default_pii=False,
            )
    except Exception:  # noqa: BLE001 - monitoring must never break the app
        logging.warning("Sentry SDK unavailable or not configured", exc_info=True)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(psycopg.Error, _database_error_handler)
    app.include_router(api_router)
    return app


app = create_app()
