"""Application API router aggregating every resource."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.account import router as account_router
from app.api.routes.admin import router as admin_router
from app.api.routes.applications import router as applications_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.internal import router as internal_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.opportunities import router as opportunities_router
from app.api.routes.profile import router as profile_router
from app.api.routes.resumes import router as resumes_router
from app.api.routes.saved import router as saved_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(opportunities_router)
router.include_router(saved_router)
router.include_router(resumes_router)
router.include_router(applications_router)
router.include_router(notifications_router)
router.include_router(account_router)
router.include_router(admin_router)
router.include_router(internal_router)
