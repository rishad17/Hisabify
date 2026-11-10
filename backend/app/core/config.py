"""Application settings, loaded from environment variables (and `.env` in development).

Every secret lives here and ONLY on the server. The frontend never sees these values.
"""

from functools import lru_cache
from typing import Literal

from fastapi import Request
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Hisabify"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Comma-separated list of allowed browser origins, e.g.
    # "http://localhost:5173,https://hisabify.vercel.app"
    cors_origins: str = Field(default="http://localhost:5173")

    # Business timezone: "ajke"/"today" is always resolved in Dhaka time, never UTC.
    default_timezone: str = "Asia/Dhaka"

    # --- Database (Supabase Postgres) ---
    database_url: str | None = None

    # --- Auth (Supabase) ---
    # Used to build the JWKS URL and to check the token's "iss" claim.
    supabase_url: str | None = None
    # Only for older projects still signing tokens with the legacy shared secret (HS256).
    # New projects use asymmetric signing keys published via JWKS — leave this empty.
    supabase_jwt_secret: str | None = None
    # SECRET admin key (sb_secret_… or legacy service_role). Only used to delete a user's
    # sign-in when they delete their account. Never expose it to the frontend.
    supabase_service_role_key: str | None = None

    # --- AI ---
    gemini_api_key: str | None = None
    # Primary model + fallback used when the primary is overloaded (HTTP 429/503) or slow.
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_model: str | None = "gemini-3.1-flash-lite"
    gemini_timeout_seconds: float = 20.0
    # Per-user limit on AI requests (protects the free quota from loops/abuse).
    ai_requests_per_minute: int = 10
    groq_api_key: str | None = None  # Phase 5

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str | None) -> str | None:
        """Supabase shows `postgresql://…`; SQLAlchemy needs to be told to use psycopg 3."""
        if not value:
            return None
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator("supabase_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once (used by create_app and scripts)."""
    return Settings()


def settings_dep(request: Request) -> Settings:
    """FastAPI dependency: the Settings instance this app was created with.

    Routes use this instead of get_settings() so tests can build an app with custom settings.
    """
    return request.app.state.settings
