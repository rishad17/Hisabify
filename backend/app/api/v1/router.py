"""Aggregates every /api/v1 router. Each phase adds `include_router` lines here."""

from fastapi import APIRouter

from app.api.v1 import analytics, categories, me, transactions, wallets

api_router = APIRouter()
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
