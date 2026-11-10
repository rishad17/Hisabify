"""User data rights: export, wipe financial data, delete the account.

Deletion order matters: several foreign keys are RESTRICT on purpose (a wallet can't
disappear while transactions point at it), so we delete children before parents
explicitly instead of relying on cascades. Everything runs in ONE database transaction:
either all of the user's data is gone, or nothing is.
"""

import csv
import io
import logging
import uuid
from collections.abc import Iterator

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import AppError
from app.models import (
    AIInteraction,
    Budget,
    Category,
    ExpectedIncome,
    Profile,
    RecurringBill,
    SavingsGoal,
    Transaction,
    Wallet,
)

logger = logging.getLogger(__name__)


def wipe_user_data(db: Session, user_id: uuid.UUID) -> None:
    """Delete ALL of the user's rows. The next GET /me re-creates a fresh default setup."""
    for stmt in (
        delete(AIInteraction).where(AIInteraction.user_id == user_id),
        delete(Budget).where(Budget.user_id == user_id),  # cascades items + adjustments
        delete(ExpectedIncome).where(ExpectedIncome.user_id == user_id),
        delete(SavingsGoal).where(SavingsGoal.user_id == user_id),
        delete(Transaction).where(Transaction.user_id == user_id),
        delete(RecurringBill).where(RecurringBill.user_id == user_id),
        delete(Wallet).where(Wallet.user_id == user_id),
        delete(Category).where(Category.user_id == user_id),
        delete(Profile).where(Profile.id == user_id),
    ):
        db.execute(stmt)
    db.commit()
    logger.info("Wiped all data for a user")  # no user id/PII in logs


def delete_auth_user(supabase_url: str, service_key: str, user_id: uuid.UUID) -> None:
    """Remove the login itself via the Supabase Auth admin API (server-side secret key)."""
    headers = {"apikey": service_key}
    if not service_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {service_key}"  # legacy service_role JWT
    try:
        response = httpx.delete(
            f"{supabase_url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=10
        )
    except httpx.HTTPError as exc:
        raise AppError("auth_delete_failed", "Couldn't reach the sign-in service.", 502) from exc
    if response.status_code not in (200, 204, 404):
        logger.warning("Supabase admin delete returned %s", response.status_code)
        raise AppError("auth_delete_failed", "Couldn't delete the sign-in account.", 502)


# ------------------------------------------------------------------ export

CSV_COLUMNS = ["date", "type", "amount", "wallet", "to_wallet", "category", "description", "source"]


def _safe(value: str | None) -> str:
    """Neutralise spreadsheet formula injection (a note like '=HYPERLINK(...)')."""
    text = value or ""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_transactions_csv(db: Session, user_id: uuid.UUID) -> Iterator[str]:
    to_wallet = aliased(Wallet)
    rows = db.execute(
        select(Transaction, Wallet.name, to_wallet.name, Category.name)
        .join(Wallet, Wallet.id == Transaction.wallet_id)
        .outerjoin(to_wallet, to_wallet.id == Transaction.to_wallet_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id, Transaction.voided_at.is_(None))
        .order_by(Transaction.occurred_on, Transaction.created_at)
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    # UTF-8 BOM so Excel shows Bangla text correctly.
    yield "﻿"
    writer.writerow(CSV_COLUMNS)
    for tx, wallet, to_name, category in rows:
        writer.writerow(
            [
                tx.occurred_on.isoformat(),
                tx.type,
                f"{tx.amount:.2f}",
                _safe(wallet),
                _safe(to_name),
                _safe(category),
                _safe(tx.description),
                tx.source,
            ]
        )
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
    yield buffer.getvalue()
