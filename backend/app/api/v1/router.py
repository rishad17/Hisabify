"""Aggregates every /api/v1 router. Each phase adds one `include_router` line here."""

from fastapi import APIRouter

api_router = APIRouter()

# Phase 1: api_router.include_router(me.router, prefix="/me", tags=["me"])
# Phase 2: wallets, categories, transactions ...
