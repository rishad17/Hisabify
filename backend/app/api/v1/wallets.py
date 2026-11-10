import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.transaction import TransactionOut
from app.schemas.wallet import SetBalance, WalletCreate, WalletOut, WalletUpdate
from app.services import ledger

router = APIRouter()


def _out(item: ledger.WalletWithBalance) -> WalletOut:
    w = item.wallet
    return WalletOut(
        id=w.id,
        name=w.name,
        type=w.type,
        opening_balance=w.opening_balance,
        balance=item.balance,
        is_default=w.is_default,
    )


@router.get("", response_model=list[WalletOut])
def list_wallets(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WalletOut]:
    """Active wallets with their current (derived) balances. Default wallet first."""
    return [_out(item) for item in ledger.list_wallets(db, user.id)]


@router.post("", response_model=WalletOut, status_code=201)
def create_wallet(
    body: WalletCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WalletOut:
    wallet = ledger.create_wallet(db, user.id, **body.model_dump())
    return _out(ledger.get_wallet(db, user.id, wallet.id))


@router.patch("/{wallet_id}", response_model=WalletOut)
def update_wallet(
    wallet_id: uuid.UUID,
    body: WalletUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WalletOut:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    ledger.update_wallet(db, user.id, wallet_id, changes)
    return _out(ledger.get_wallet(db, user.id, wallet_id))


@router.post("/{wallet_id}/archive", status_code=204)
def archive_wallet(
    wallet_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    ledger.archive_wallet(db, user.id, wallet_id)
    return Response(status_code=204)


@router.post("/{wallet_id}/set-balance", response_model=TransactionOut | None)
def set_balance(
    wallet_id: uuid.UUID,
    body: SetBalance,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict | None:
    """Returns the adjustment transaction created, or null if the balance already matched."""
    tx = ledger.set_wallet_balance(db, user.id, wallet_id, body.balance, body.note)
    if tx is None:
        return None
    return ledger.load_out(db, user.id, [tx.id])[0]
