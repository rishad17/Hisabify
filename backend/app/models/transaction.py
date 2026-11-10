import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import MONEY, CreatedAt, UpdatedAt, UserId, UuidPk, in_list

TRANSACTION_TYPES = ("expense", "income", "transfer", "adjustment")
TRANSACTION_SOURCES = ("manual", "text", "voice")


class Transaction(Base):
    """One money movement.

    * expense / income → `wallet_id` + `category_id`, amount > 0
    * transfer         → from `wallet_id` to `to_wallet_id`, no category, never counted
                         as spending
    * adjustment       → "set balance to X" correction; signed amount, no category

    Rows are never deleted by normal use — they are *voided* (voided_at), which keeps
    history and makes derived balances recompute automatically.

    Duplicate protection: the client sends one Idempotency-Key per confirmed batch;
    each row stores it with its position in the batch. A retried request hits the
    unique constraint and returns the already-saved rows instead of inserting twice.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(in_list("type", TRANSACTION_TYPES), name="type"),
        CheckConstraint(in_list("source", TRANSACTION_SOURCES), name="source"),
        CheckConstraint(
            "(type = 'adjustment' AND amount <> 0) OR (type <> 'adjustment' AND amount > 0)",
            name="amount_sign",
        ),
        CheckConstraint(
            "(type = 'transfer') = (to_wallet_id IS NOT NULL)", name="transfer_has_target"
        ),
        CheckConstraint(
            "to_wallet_id IS NULL OR to_wallet_id <> wallet_id", name="transfer_distinct_wallets"
        ),
        CheckConstraint(
            "(type IN ('expense', 'income')) = (category_id IS NOT NULL)",
            name="category_matches_type",
        ),
        UniqueConstraint("user_id", "idempotency_key", "batch_index"),
        Index(
            "ix_transactions_user_date_active",
            "user_id",
            text("occurred_on DESC"),
            postgresql_where=text("voided_at IS NULL"),
        ),
        Index("ix_transactions_user_category_date", "user_id", "category_id", "occurred_on"),
        Index(
            "ix_transactions_to_wallet",
            "to_wallet_id",
            postgresql_where=text("to_wallet_id IS NOT NULL"),
        ),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    type: Mapped[str] = mapped_column(String(12))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="RESTRICT"), index=True
    )
    to_wallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="RESTRICT")
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    recurring_bill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recurring_bills.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(String(200))
    occurred_on: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(10), server_default=text("'manual'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    batch_index: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
