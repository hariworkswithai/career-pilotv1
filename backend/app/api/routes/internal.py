"""Internal ingest endpoint invoked by the scheduled sync job (GitHub Actions)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_repository
from app.core.config import get_settings
from app.core.security import require_internal_token
from app.db.base import Repository
from app.schemas.operations import SyncResult
from app.services.providers import AshbyAdapter, GreenhouseAdapter, LeverAdapter
from app.services.providers.base import BaseProvider
from app.services.providers.pipeline import run_ingestion
from app.services.providers.registry import SUPPORTED_PROVIDERS, adapter_for

router = APIRouter(prefix="/internal/sync", tags=["internal"], dependencies=[Depends(require_internal_token)])


def _env_providers() -> list[BaseProvider]:
    settings = get_settings()
    return [
        GreenhouseAdapter(settings.greenhouse_board_tokens),
        AshbyAdapter(settings.ashby_board_names),
        LeverAdapter(settings.lever_board_names),
    ]


def _repo_providers(repository: Repository) -> list[BaseProvider]:
    """Adapters for admin-registered active sources, grouped by provider."""
    by_provider: dict[str, list[str]] = {}
    for source in repository.list_sources():
        if not source.is_active or source.source_type not in SUPPORTED_PROVIDERS:
            continue
        by_provider.setdefault(source.source_type, [])
        if source.board_identifier not in by_provider[source.source_type]:
            by_provider[source.source_type].append(source.board_identifier)
    providers: list[BaseProvider] = []
    for provider_name, keys in by_provider.items():
        try:
            providers.append(adapter_for(provider_name, keys))
        except ValueError:
            continue
    return providers


def _record_source_health(repository: Repository, result: SyncResult) -> None:
    """Map ingestion errors back onto registered sources (success by default).

    A source is unhealthy when a provider-level failure or its own key appears
    in the error list. Existing jobs are never touched here — freshness is
    handled inside `run_ingestion`, which only sweeps successful providers.
    """
    hard_failed = {err.split(":", 1)[0] for err in result.errors if "/" not in err.split(":", 1)[0]}
    for source in repository.list_sources():
        if not source.is_active:
            repository.record_source_sync(source.id, success=False, error="Source disabled")
            continue
        key_marker = f"{source.source_type}/{source.board_identifier}"
        failed = source.source_type in hard_failed or any(key_marker in err for err in result.errors)
        first_error = next((e for e in result.errors if key_marker in e or e.startswith(source.source_type + ":")), "")
        repository.record_source_sync(source.id, success=not failed, error=first_error)


@router.post("", response_model=SyncResult)
async def trigger_sync(repository: Repository = Depends(get_repository)) -> SyncResult:
    providers = _env_providers() + _repo_providers(repository)
    result = await run_ingestion(repository, providers)
    _record_source_health(repository, result)
    return result
