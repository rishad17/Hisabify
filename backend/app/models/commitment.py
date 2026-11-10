"""Money that is *promised* but not yet moved: bills, expected income, savings goals.
These power commitment-aware "safe to spend" and the purchase simulator."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import MONEY, CreatedAt, UserId, UuidPk, in_list


class RecurringBill(Base):
    """A monthly bill (rent, internet, tuition fee…). A month's bill counts as paid when
    a transaction in that month links to it via transactions.recurring_bill_id."""

    __tablename__ = "recurring_bills"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("due_day BETWEEN 1 AND 31", name="due_day_range"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    name: Mapped[str] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="SET NULL")
    )
    due_day: Mapped[int] = mapped_column(SmallInteger)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[CreatedAt]


class ExpectedIncome(Base):
    """Income the user expects but has not received (tuition fee, freelance payment,
    allowance). Kept separate from real income so plans can show 'confirmed money'
    vs 'if this arrives' — key for irregular earners."""

    __tablename__ = "expected_incomes"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(in_list("status", ("expected", "received", "cancelled")), name="status"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    source: Mapped[str] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    expected_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), server_default=text("'expected'"))
    received_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL")
    )
    created_at: Mapped[CreatedAt]


class SavingsGoal(Base):
    __tablename__ = "savings_goals"
    __table_args__ = (CheckConstraint("target_amount > 0", name="target_positive"),)

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    name: Mapped[str] = mapped_column(String(80))
    target_amount: Mapped[Decimal] = mapped_column(MONEY)
    deadline: Mapped[date | None] = mapped_column(Date)
    # Optional: progress = balance of a dedicated savings wallet.
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="SET NULL")
    )
    created_at: Mapped[CreatedAt]
