"""Aggregates every /api/v1 router. Each phase adds `include_router` lines here."""

from fastapi import APIRouter

from app.api.v1 import categories, me

api_router = APIRouter()
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
