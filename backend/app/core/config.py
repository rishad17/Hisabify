"""Application settings, loaded from environment variables (and `.env` in development).

Every secret lives here and ONLY on the server. The frontend never sees these values.
"""

from functools import lru_cache
from typing import Literal

from fastapi import Request
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TakaWise AI"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Comma-separated list of allowed browser origins, e.g.
    # "http://localhost:5173,https://takawise.vercel.app"
    cors_origins: str = Field(default="http://localhost:5173")

    # Business timezone: "ajke"/"today" is always resolved in Dhaka time, never UTC.
    default_timezone: str = "Asia/Dhaka"

    # --- Added in later phases (declared now so .env.example stays the single reference) ---
    database_url: str | None = None  # Phase 1
    supabase_url: str | None = None  # Phase 1 (JWT verification)
    gemini_api_key: str | None = None  # Phase 4
    groq_api_key: str | None = None  # Phase 5

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
