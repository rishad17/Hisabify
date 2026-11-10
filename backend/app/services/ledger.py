"""The ledger: wallets, transactions and balances.

Key design decisions (see README / architecture notes):

1. **Balances are derived, never stored.**
       balance = opening_balance
               + income − expense            (rows where wallet_id = this wallet)
               − transfers out + transfers in
               + adjustments                 (signed)
   counting only non-voided rows. Editing or voiding any transaction automatically
   gives correct balances; there is no "balance" column that can drift.

2. **Every query is scoped by user_id.** Helper `_owned_wallet` / `_owned_category`
   return 404 for anything that doesn't belong to the caller, so one user can never
   reference another user's wallet or category, even by guessing an id.

3. **The DB constraints are the last line of defense**, but we validate here first so
   users get friendly error messages instead of raw IntegrityErrors.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, case, func, literal, or_, select, union_all, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.errors import AppError
from app.models import Category, Profile, Transaction, Wallet
from app.schemas.transaction import TransactionIn, TransactionUpdate

ZERO = Decimal("0.00")
EARLIEST_DATE = date(2000, 1, 1)


# --------------------------------------------------------------------- helpers


def today_for(db: Session, user_id: uuid.UUID) -> date:
    """'Today' in the user's timezone (Asia/Dhaka by default), never the server's."""
    tz = db.scalar(select(Profile.timezone).where(Profile.id == user_id)) or "Asia/Dhaka"
    return datetime.now(ZoneInfo(tz)).date()


def _not_found(what: str) -> AppError:
    return AppError(f"{what}_not_found", f"{what.capitalize()} not found.", status_code=404)


def _invalid(code: str, message: str) -> AppError:
    return AppError(code, message, status_code=422)


def _owned_wallet(db: Session, user_id: uuid.UUID, wallet_id: uuid.UUID) -> Wallet:
    wallet = db.scalar(select(Wallet).where(Wallet.id == wallet_id, Wallet.user_id == user_id))
    if wallet is None:
        raise _not_found("wallet")
    return wallet


def _owned_category(db: Session, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    if category is None:
        raise _not_found("category")
    return category


# -------------------------------------------------------------------- balances


def _deltas_query(user_id: uuid.UUID) -> Select:
    """One row per (wallet, signed amount) for every active transaction."""
    t = Transaction
    outgoing = select(
        t.wallet_id.label("wallet_id"),
        case(
            (t.type.in_(("expense", "transfer")), -t.amount),
            else_=t.amount,  # income, adjustment (adjustment is already signed)
        ).label("delta"),
    ).where(t.user_id == user_id, t.voided_at.is_(None))
    incoming = select(t.to_wallet_id.label("wallet_id"), t.amount.label("delta")).where(
        t.user_id == user_id, t.voided_at.is_(None), t.type == "transfer"
    )
    return union_all(outgoing, incoming)


def wallet_balances(db: Session, user_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    deltas = _deltas_query(user_id).subquery()
    sums = (
        select(deltas.c.wallet_id, func.sum(deltas.c.delta).label("total"))
        .group_by(deltas.c.wallet_id)
        .subquery()
    )
    rows = db.execute(
        select(Wallet.id, Wallet.opening_balance + func.coalesce(sums.c.total, 0))
        .outerjoin(sums, sums.c.wallet_id == Wallet.id)
        .where(Wallet.user_id == user_id)
    ).all()
    return {wallet_id: Decimal(balance).quantize(ZERO) for wallet_id, balance in rows}


# --------------------------------------------------------------------- wallets


@dataclass
class WalletWithBalance:
    wallet: Wallet
    balance: Decimal


def list_wallets(db: Session, user_id: uuid.UUID) -> list[WalletWithBalance]:
    wallets = db.scalars(
        select(Wallet)
        .where(Wallet.user_id == user_id, Wallet.archived_at.is_(None))
        .order_by(Wallet.is_default.desc(), Wallet.created_at)
    ).all()
    balances = wallet_balances(db, user_id)
    return [WalletWithBalance(w, balances.get(w.id, w.opening_balance)) for w in wallets]


def get_wallet(db: Session, user_id: uuid.UUID, wallet_id: uuid.UUID) -> WalletWithBalance:
    wallet = _owned_wallet(db, user_id, wallet_id)
    return WalletWithBalance(wallet, wallet_balances(db, user_id).get(wallet.id, ZERO))


def _name_taken(db: Session, user_id: uuid.UUID, name: str, exclude: uuid.UUID | None) -> bool:
    stmt = select(Wallet.id).where(
        Wallet.user_id == user_id, func.lower(Wallet.name) == name.lower()
    )
    if exclude:
        stmt = stmt.where(Wallet.id != exclude)
    return db.scalar(stmt) is not None


def _clear_default(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(Wallet).where(Wallet.user_id == user_id, Wallet.is_default).values(is_default=False)
    )
    db.flush()


def create_wallet(
    db: Session,
    user_id: uuid.UUID,
    *,
    name: str,
    type: str,
    opening_balance: Decimal,
    is_default: bool,
) -> Wallet:
    if _name_taken(db, user_id, name, None):
        raise AppError("wallet_name_taken", f'You already have a wallet named "{name}".', 409)
    if is_default:
        _clear_default(db, user_id)
    wallet = Wallet(
        user_id=user_id,
        name=name,
        type=type,
        opening_balance=opening_balance,
        is_default=is_default,
    )
    db.add(wallet)
    db.commit()
    return wallet


def update_wallet(db: Session, user_id: uuid.UUID, wallet_id: uuid.UUID, changes: dict) -> Wallet:
    wallet = _owned_wallet(db, user_id, wallet_id)
    if wallet.archived_at is not None:
        raise _invalid("wallet_archived", "This wallet is archived.")
    if "name" in changes and _name_taken(db, user_id, changes["name"], wallet.id):
        raise AppError(
            "wallet_name_taken", f'You already have a wallet named "{changes["name"]}".', 409
        )
    if changes.get("is_default"):
        _clear_default(db, user_id)
    for field, value in changes.items():
        setattr(wallet, field, value)
    db.commit()
    return wallet


def archive_wallet(db: Session, user_id: uuid.UUID, wallet_id: uuid.UUID) -> None:
    """Hide a wallet from pickers. Its history stays intact (and keeps counting in reports)."""
    wallet = _owned_wallet(db, user_id, wallet_id)
    if wallet.is_default:
        raise _invalid(
            "cannot_archive_default", "Make another wallet the default before archiving this one."
        )
    if wallet.archived_at is None:
        wallet.archived_at = datetime.now(UTC)
        db.commit()


def set_wallet_balance(
    db: Session, user_id: uuid.UUID, wallet_id: uuid.UUID, target: Decimal, note: str | None
) -> Transaction | None:
    """Correct a wallet to its real-world balance by recording the difference as an
    `adjustment`. Returns None if the balance was already correct."""
    current = get_wallet(db, user_id, wallet_id)
    if current.wallet.archived_at is not None:
        raise _invalid("wallet_archived", "This wallet is archived.")
    delta = (target - current.balance).quantize(ZERO)
    if delta == 0:
        return None
    tx = Transaction(
        user_id=user_id,
        type="adjustment",
        amount=delta,
        wallet_id=wallet_id,
        description=note or "Balance correction",
        occurred_on=today_for(db, user_id),
        source="manual",
    )
    db.add(tx)
    db.commit()
    return tx


# ---------------------------------------------------------------- transactions


@dataclass
class TxFields:
    """Fully-resolved transaction fields, validated by `_validate`."""

    type: str
    amount: Decimal
    wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID | None
    category_id: uuid.UUID | None
    description: str | None
    occurred_on: date


def _validate(db: Session, user_id: uuid.UUID, f: TxFields, *, today: date) -> None:
    """All business rules for an expense / income / transfer (used for create AND edit).

    Archived wallets/categories can't be used: to edit an old transaction from an archived
    wallet, the user first moves it to an active one (or un-archives — a later feature).
    """
    wallet = _owned_wallet(db, user_id, f.wallet_id)
    if wallet.archived_at is not None:
        raise _invalid("wallet_archived", f'Wallet "{wallet.name}" is archived.')

    if f.occurred_on > today:
        raise _invalid("date_in_future", "Transactions can't be dated in the future.")
    if f.occurred_on < EARLIEST_DATE:
        raise _invalid("date_too_old", "That date is too far in the past.")

    if f.type == "transfer":
        if f.to_wallet_id is None:
            raise _invalid("transfer_needs_target", "Choose the wallet you're moving money to.")
        if f.to_wallet_id == f.wallet_id:
            raise _invalid("transfer_same_wallet", "Pick two different wallets for a transfer.")
        target = _owned_wallet(db, user_id, f.to_wallet_id)
        if target.archived_at is not None:
            raise _invalid("wallet_archived", f'Wallet "{target.name}" is archived.')
        if f.category_id is not None:
            raise _invalid("transfer_has_category", "Transfers don't have a category.")
        return

    # expense / income
    if f.to_wallet_id is not None:
        raise _invalid("unexpected_target_wallet", "Only transfers have a destination wallet.")
    if f.category_id is None:
        raise _invalid("category_required", "Choose a category.")
    category = _owned_category(db, user_id, f.category_id)
    if category.archived_at is not None:
        raise _invalid("category_archived", f'Category "{category.name}" is archived.')
    if category.kind != f.type:
        raise _invalid(
            "category_kind_mismatch",
            f'"{category.name}" is an {category.kind} category, not {f.type}.',
        )


def create_batch(
    db: Session,
    user_id: uuid.UUID,
    items: list[TransactionIn],
    *,
    idempotency_key: str,
    source: str,
) -> tuple[list[Transaction], bool]:
    """Save several transactions atomically: all of them, or none.

    Returns (rows, replayed). If this Idempotency-Key was already used, the original rows
    are returned and nothing new is written — so a double-click, a retry after a timeout,
    or a flaky mobile connection can never create duplicates.
    """
    existing = _rows_for_key(db, user_id, idempotency_key)
    if existing:
        return existing, True

    today = today_for(db, user_id)
    rows: list[Transaction] = []
    for index, item in enumerate(items):
        fields = TxFields(
            type=item.type,
            amount=item.amount,
            wallet_id=item.wallet_id,
            to_wallet_id=item.to_wallet_id,
            category_id=item.category_id,
            description=item.description,
            occurred_on=item.occurred_on or today,
        )
        try:
            _validate(db, user_id, fields, today=today)
        except AppError as exc:
            # Tell the client which item failed (matters for multi-item AI drafts).
            exc.details = {"item_index": index}
            raise
        rows.append(
            Transaction(
                user_id=user_id,
                source=source,
                idempotency_key=idempotency_key,
                batch_index=index,
                **fields.__dict__,
            )
        )

    db.add_all(rows)
    try:
        db.commit()
    except IntegrityError:
        # Two identical requests raced each other and the other one won: return its rows.
        db.rollback()
        existing = _rows_for_key(db, user_id, idempotency_key)
        if existing:
            return existing, True
        raise
    return rows, False


def _rows_for_key(db: Session, user_id: uuid.UUID, key: str) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.idempotency_key == key)
            .order_by(Transaction.batch_index)
        )
    )


def _owned_transaction(db: Session, user_id: uuid.UUID, tx_id: uuid.UUID) -> Transaction:
    tx = db.scalar(
        select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user_id)
    )
    if tx is None:
        raise _not_found("transaction")
    return tx


def update_transaction(
    db: Session, user_id: uuid.UUID, tx_id: uuid.UUID, patch: TransactionUpdate
) -> Transaction:
    tx = _owned_transaction(db, user_id, tx_id)
    if tx.voided_at is not None:
        raise _invalid("transaction_voided", "This transaction was deleted and can't be edited.")
    if tx.type == "adjustment":
        raise _invalid(
            "adjustment_not_editable", "Balance corrections can't be edited — delete it instead."
        )

    changes = patch.model_dump(exclude_unset=True)
    merged = TxFields(
        type=tx.type,
        amount=tx.amount,
        wallet_id=tx.wallet_id,
        to_wallet_id=tx.to_wallet_id,
        category_id=tx.category_id,
        description=tx.description,
        occurred_on=tx.occurred_on,
    )
    for field, value in changes.items():
        setattr(merged, field, value)

    # Switching type clears fields that no longer apply, unless the client set them.
    if "type" in changes and changes["type"] != tx.type:
        if merged.type == "transfer" and "category_id" not in changes:
            merged.category_id = None
        if merged.type != "transfer" and "to_wallet_id" not in changes:
            merged.to_wallet_id = None
        if merged.type != "transfer" and tx.type != "transfer" and "category_id" not in changes:
            merged.category_id = None  # expense <-> income needs a new category

    _validate(db, user_id, merged, today=today_for(db, user_id))
    for field, value in merged.__dict__.items():
        setattr(tx, field, value)
    db.commit()
    return tx


def void_transaction(db: Session, user_id: uuid.UUID, tx_id: uuid.UUID) -> Transaction:
    """Soft-delete: the row stays for history but stops counting everywhere."""
    tx = _owned_transaction(db, user_id, tx_id)
    if tx.voided_at is None:
        tx.voided_at = datetime.now(UTC)
        db.commit()
    return tx


# ------------------------------------------------------------- listing / reads


@dataclass
class TxFilters:
    month: date | None = None  # first day of month
    wallet_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    type: str | None = None
    include_voided: bool = False


def month_range(month: date) -> tuple[date, date]:
    """[first day of month, first day of next month)"""
    start = month.replace(day=1)
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, end


def list_transactions(
    db: Session, user_id: uuid.UUID, filters: TxFilters, *, limit: int, offset: int
) -> tuple[list[dict], int]:
    t = Transaction
    w_from = aliased(Wallet)
    w_to = aliased(Wallet)
    conditions = [t.user_id == user_id]
    if not filters.include_voided:
        conditions.append(t.voided_at.is_(None))
    if filters.month:
        start, end = month_range(filters.month)
        conditions += [t.occurred_on >= start, t.occurred_on < end]
    if filters.wallet_id:
        conditions.append(
            or_(t.wallet_id == filters.wallet_id, t.to_wallet_id == filters.wallet_id)
        )
    if filters.category_id:
        conditions.append(t.category_id == filters.category_id)
    if filters.type:
        conditions.append(t.type == filters.type)
    where = and_(*conditions)

    total = db.scalar(select(func.count()).select_from(t).where(where)) or 0
    rows = db.execute(
        select(t, w_from.name, w_to.name, Category)
        .join(w_from, w_from.id == t.wallet_id)
        .outerjoin(w_to, w_to.id == t.to_wallet_id)
        .outerjoin(Category, Category.id == t.category_id)
        .where(where)
        .order_by(t.occurred_on.desc(), t.created_at.desc(), t.batch_index.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [to_out(tx, wn, twn, cat) for tx, wn, twn, cat in rows], total


def load_out(db: Session, user_id: uuid.UUID, tx_ids: list[uuid.UUID]) -> list[dict]:
    """Response-shaped rows (with wallet/category names) for the given ids, in order."""
    if not tx_ids:
        return []
    w_from, w_to = aliased(Wallet), aliased(Wallet)
    rows = db.execute(
        select(Transaction, w_from.name, w_to.name, Category)
        .join(w_from, w_from.id == Transaction.wallet_id)
        .outerjoin(w_to, w_to.id == Transaction.to_wallet_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id, Transaction.id.in_(tx_ids))
    ).all()
    by_id = {tx.id: to_out(tx, wn, twn, cat) for tx, wn, twn, cat in rows}
    return [by_id[i] for i in tx_ids if i in by_id]


def to_out(tx: Transaction, wallet_name: str, to_wallet_name: str | None, cat) -> dict:
    return {
        "id": tx.id,
        "type": tx.type,
        "amount": tx.amount,
        "wallet_id": tx.wallet_id,
        "wallet_name": wallet_name,
        "to_wallet_id": tx.to_wallet_id,
        "to_wallet_name": to_wallet_name,
        "category": (
            {"id": cat.id, "name": cat.name, "name_bn": cat.name_bn, "icon": cat.icon}
            if cat is not None
            else None
        ),
        "description": tx.description,
        "occurred_on": tx.occurred_on,
        "source": tx.source,
        "voided": tx.voided_at is not None,
        "created_at": tx.created_at,
    }


# ------------------------------------------------------------------- overview


def month_overview(db: Session, user_id: uuid.UUID, month: date) -> dict:
    """Totals for the dashboard cards. Transfers and adjustments are NOT income/expense."""
    start, end = month_range(month)
    t = Transaction
    income, expense, count = db.execute(
        select(
            func.coalesce(func.sum(case((t.type == "income", t.amount), else_=literal(0))), 0),
            func.coalesce(func.sum(case((t.type == "expense", t.amount), else_=literal(0))), 0),
            func.count(),
        ).where(
            t.user_id == user_id,
            t.voided_at.is_(None),
            t.occurred_on >= start,
            t.occurred_on < end,
            t.type.in_(("income", "expense")),
        )
    ).one()
    total_balance = sum((w.balance for w in list_wallets(db, user_id)), ZERO)
    income, expense = Decimal(income).quantize(ZERO), Decimal(expense).quantize(ZERO)
    return {
        "month": start.strftime("%Y-%m"),
        "total_balance": total_balance,
        "income": income,
        "expense": expense,
        "net": income - expense,
        "transaction_count": count,
    }
