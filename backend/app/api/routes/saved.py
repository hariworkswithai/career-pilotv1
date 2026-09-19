"""Saved opportunities endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_repository
from app.core.security import VerifiedUser, current_user
from app.db.base import Repository
from app.schemas.opportunities import OpportunityRecord

router = APIRouter(prefix="/saved", tags=["saved"])


@router.get("", response_model=list[OpportunityRecord])
async def list_saved(
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> list[OpportunityRecord]:
    ids = repository.list_saved(user.user_id)
    records: list[OpportunityRecord] = []
    for opp_id in ids:
        record = repository.get_opportunity(opp_id)
        if record:
            records.append(record)
    return records


@router.put("/{opportunity_id}")
async def add_saved(
    opportunity_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    if not repository.get_opportunity(opportunity_id):
        raise HTTPException(status_code=404, detail="Opportunity not found")
    repository.add_saved(user.user_id, opportunity_id)
    return {"saved": True}


@router.delete("/{opportunity_id}")
async def remove_saved(
    opportunity_id: str,
    user: VerifiedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> dict:
    repository.remove_saved(user.user_id, opportunity_id)
    return {"saved": False}
