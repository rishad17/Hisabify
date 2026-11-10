"""FastAPI entry point.

Run locally:  uvicorn app.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.llm_client import GeminiClient
from app.ai.rate_limit import RateLimiter
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.db import make_engine, make_session_factory
from app.core.errors import register_error_handlers
from app.core.security import TokenVerifier
from app.voice.transcriber import SpeechTranscriber


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        if app.state.engine is not None:
            app.state.engine.dispose()  # close pooled DB connections on shutdown

    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        version=settings.app_version,
        # Interactive docs are handy locally but needn't be public in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # we send a Bearer token, not cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    app.state.settings = settings

    # Database: create_engine() does not connect yet — connections open on first use.
    app.state.engine = make_engine(settings.database_url) if settings.database_url else None
    app.state.session_factory = (
        make_session_factory(app.state.engine) if app.state.engine is not None else None
    )

    # Auth: verifies Supabase access tokens (public keys fetched lazily from JWKS).
    app.state.token_verifier = (
        TokenVerifier(settings.supabase_url, settings.supabase_jwt_secret)
        if settings.supabase_url
        else None
    )

    # AI: Gemini client (None if no key → AI endpoints answer 503 "not configured").
    app.state.llm = (
        GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            fallback_model=settings.gemini_fallback_model,
            timeout_seconds=settings.gemini_timeout_seconds,
        )
        if settings.gemini_api_key
        else None
    )
    app.state.ai_rate_limiter = RateLimiter(settings.ai_requests_per_minute)
    # Voice: Gemini transcription, with optional Groq Whisper as a last fallback.
    app.state.transcriber = (
        SpeechTranscriber(app.state.llm, settings.groq_api_key)
        if app.state.llm is not None or settings.groq_api_key
        else None
    )

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
