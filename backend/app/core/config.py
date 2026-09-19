"""Application configuration loaded from environment variables.

Secrets are read only here and are never exposed by any other module.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    environment: str = "development"
    log_level: str = "INFO"
    webapp_url: str = "http://localhost:3000"
    api_cors_origins: str = "http://localhost:3000"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # AI
    ai_provider: str = "openrouter"  # "openrouter" | "groq" (OpenAI-compatible)
    ai_api_key: str = ""
    ai_base_url: str = ""  # optional override of the provider default endpoint
    ai_model: str = "openai/gpt-4o-mini"  # enhancement + tailoring
    ai_parse_model: str = "google/gemini-flash-1.5"  # structured resume parsing
    ai_json_model: str = ""
    ai_max_tokens: int = 2048
    ai_timeout_ms: int = 60_000
    ai_retries: int = 2
    # Monthly free-tier quota (per feature)
    ai_quota_enhancements: int = 3
    ai_quota_tailorings: int = 3

    # Email
    resend_api_key: str = ""
    resend_from_email: str = ""

    # Monitoring
    sentry_dsn: str = ""

    # Internal endpoints
    internal_sync_token: str = ""

    # Providers
    greenhouse_sources: str = ""
    ashby_sources: str = ""
    lever_sources: str = ""

    # Persistence
    repository_backend: str = "inmemory"  # "inmemory" (dev) | "postgres" (prod)
    database_url: str = ""  # canonical server-only Postgres URL, e.g. Supabase pooled port 6543
    postgres_dsn: str = ""  # legacy alias for database_url (fallback only)
    storage_backend: str = "local"  # "local" (dev) | "supabase" (prod bucket `user-files`)
    supabase_storage_bucket: str = "user-files"

    # Limits
    resume_max_mb: int = 10
    rate_limit_per_minute: int = 120
    signed_url_ttl_seconds: int = 900

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def greenhouse_board_tokens(self) -> list[str]:
        return self._csv(self.greenhouse_sources)

    @property
    def ashby_board_names(self) -> list[str]:
        return self._csv(self.ashby_sources)

    @property
    def lever_board_names(self) -> list[str]:
        return self._csv(self.lever_sources)

    @property
    def json_model(self) -> str:
        return self.ai_json_model or self.ai_model

    @property
    def has_supabase_credentials(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def has_postgres_dsn(self) -> bool:
        """True when either database connection variable is configured."""
        return bool(self.database_url or self.postgres_dsn)

    @property
    def resolved_postgres_dsn(self) -> str:
        """Connection string for PostgresRepository. DATABASE_URL wins;
        POSTGRES_DSN is kept as a legacy fallback."""
        return self.database_url or self.postgres_dsn

    @property
    def resume_max_bytes(self) -> int:
        return self.resume_max_mb * 1024 * 1024

    @staticmethod
    def _csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
