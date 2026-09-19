"""Profile and preferences endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_repository
from app.core.security import VerifiedUser, current_user
from app.db.base import Repository
from app.schemas.common import WorkMode
from app.schemas.profiles import (
    ApplicationAnswerProfile,
    ApplicationPreferences,
    JobPreferences,
    NotificationPreferences,
    OnboardingRequest,
    OnboardingResult,
    Profile,
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/onboarding", response_model=OnboardingResult)
async def complete_onboarding(
    payload: OnboardingRequest,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> OnboardingResult:
    """Finish the initial onboarding survey.

    Target role is required (schema-enforced, 422 when missing). Every other field is
    optional and merged over existing data, so resume-derived information already in the
    profile is never clobbered or re-requested.
    """
    profile = repository.get_profile(user.user_id) or Profile(user_id=user.user_id)
    if payload.full_name:
        profile.full_name = payload.full_name
    if payload.city:
        profile.city = payload.city
    profile.onboarding_completed = True

    prefs = repository.get_job_preferences(user.user_id) or JobPreferences(user_id=user.user_id)
    prefs.target_roles = [r.strip() for r in payload.target_roles if r.strip()]
    prefs.employment_types = payload.employment_types or prefs.employment_types
    prefs.experience_level = payload.experience_level or prefs.experience_level

    if payload.remote_only:
        prefs.work_modes = [WorkMode.REMOTE]
        prefs.remote_ok = True
    elif payload.work_modes:
        prefs.work_modes = payload.work_modes
    elif not prefs.work_modes:
        prefs.work_modes = [WorkMode.ANY]

    if payload.anywhere_india:
        prefs.preferred_cities = ["anywhere"]
    elif payload.preferred_cities:
        cities = [c.strip() for c in payload.preferred_cities if c.strip()]
        if not payload.remote_only and cities:
            prefs.preferred_cities = cities

    repository.upsert_profile(profile)
    repository.upsert_job_preferences(prefs)
    return OnboardingResult(profile=profile, job_preferences=prefs, onboarding_completed=True)


@router.get("")
async def get_profile(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> Profile:
    return repository.get_profile(user.user_id) or Profile(user_id=user.user_id)


@router.put("", response_model=Profile)
async def update_profile(
    payload: Profile,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> Profile:
    profile = payload.model_copy(update={"user_id": user.user_id})
    repository.upsert_profile(profile)
    return profile


@router.get("/job-preferences")
async def get_job_preferences(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> JobPreferences:
    return repository.get_job_preferences(user.user_id) or JobPreferences(user_id=user.user_id)


@router.put("/job-preferences", response_model=JobPreferences)
async def update_job_preferences(
    payload: JobPreferences,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> JobPreferences:
    prefs = payload.model_copy(update={"user_id": user.user_id})
    repository.upsert_job_preferences(prefs)
    return prefs


@router.get("/application-preferences")
async def get_application_preferences(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ApplicationPreferences:
    return repository.get_application_preferences(user.user_id) or ApplicationPreferences(user_id=user.user_id)


@router.put("/application-preferences", response_model=ApplicationPreferences)
async def update_application_preferences(
    payload: ApplicationPreferences,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ApplicationPreferences:
    prefs = payload.model_copy(update={"user_id": user.user_id})
    repository.upsert_application_preferences(prefs)
    return prefs


@router.get("/notification-preferences")
async def get_notification_preferences(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> NotificationPreferences:
    return repository.get_notification_preferences(user.user_id) or NotificationPreferences(user_id=user.user_id)


@router.put("/notification-preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    payload: NotificationPreferences,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> NotificationPreferences:
    prefs = payload.model_copy(update={"user_id": user.user_id})
    repository.upsert_notification_preferences(prefs)
    return prefs


@router.get("/application-answer-profile")
async def get_answer_profile(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ApplicationAnswerProfile:
    return repository.get_answer_profile(user.user_id) or ApplicationAnswerProfile(user_id=user.user_id)


@router.put("/application-answer-profile", response_model=ApplicationAnswerProfile)
async def update_answer_profile(
    payload: ApplicationAnswerProfile,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> ApplicationAnswerProfile:
    profile = payload.model_copy(update={"user_id": user.user_id})
    repository.upsert_answer_profile(profile)
    return profile
