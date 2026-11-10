from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, settings_dep
from app.core.db import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(settings_dep)) -> HealthResponse:
    """Liveness check used by the frontend status page and the hosting provider.

    Deliberately touches no database or AI provider, so it stays fast and cheap.
    See /health/db for a database check.
    """
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


class DbHealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["reachable"]


@router.get("/health/db", response_model=DbHealthResponse)
def health_db(db: Session = Depends(get_db)) -> DbHealthResponse:
    """Readiness check: confirms the API can reach Postgres. Errors → 500/503 with the
    standard error body (no connection details are leaked)."""
    db.execute(text("SELECT 1"))
    return DbHealthResponse(status="ok", database="reachable")
