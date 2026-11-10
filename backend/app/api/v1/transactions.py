import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.schemas.transaction import (
    TransactionBatchIn,
    TransactionBatchOut,
    TransactionOut,
    TransactionPage,
    TransactionUpdate,
)
from app.services import ledger

router = APIRouter()

# A client-generated id (UUID recommended). Letters, digits, dash, underscore.
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]
MonthParam = Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-11"])]


def parse_month(month: str | None) -> date | None:
    if month is None:
        return None
    year, mon = month.split("-")
    return date(int(year), int(mon), 1)


@router.get("", response_model=TransactionPage)
def list_transactions(
    month: MonthParam = None,
    wallet_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    type: Literal["expense", "income", "transfer", "adjustment"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    filters = ledger.TxFilters(
        month=parse_month(month), wallet_id=wallet_id, category_id=category_id, type=type
    )
    items, total = ledger.list_transactions(db, user.id, filters, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/batch", response_model=TransactionBatchOut, status_code=201)
def create_batch(
    body: TransactionBatchIn,
    idempotency_key: IdempotencyKey,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Save 1–20 transactions atomically.

    Send a fresh `Idempotency-Key` for each confirmed form/draft and REUSE it when
    retrying. A repeated key returns the originally saved rows with `replayed: true`.
    """
    rows, replayed = ledger.create_batch(
        db, user.id, body.items, idempotency_key=idempotency_key, source=body.source
    )
    return {"items": ledger.load_out(db, user.id, [r.id for r in rows]), "replayed": replayed}


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: uuid.UUID,
    body: TransactionUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not body.model_fields_set:
        raise AppError("empty_update", "Nothing to update.", status_code=422)
    tx = ledger.update_transaction(db, user.id, tx_id, body)
    return ledger.load_out(db, user.id, [tx.id])[0]


@router.post("/{tx_id}/void", response_model=TransactionOut)
def void_transaction(
    tx_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """'Delete' a transaction. It stops counting in balances and reports immediately."""
    tx = ledger.void_transaction(db, user.id, tx_id)
    return ledger.load_out(db, user.id, [tx.id])[0]
