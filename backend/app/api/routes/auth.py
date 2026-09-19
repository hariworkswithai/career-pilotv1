"""Auth endpoints: identity claims for the current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import VerifiedUser, current_user

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
async def me(user: VerifiedUser = Depends(current_user)) -> dict:
    return {"user_id": user.user_id, "email": user.email, "role": user.role}
