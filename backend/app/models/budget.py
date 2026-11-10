import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import MONEY, CreatedAt, UpdatedAt, UserId, UuidPk, in_list


class Budget(Base):
    """One budget per user per calendar month (`month` is always the 1st)."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "month"),
        CheckConstraint("EXTRACT(DAY FROM month) = 1", name="month_is_first_day"),
        CheckConstraint(in_list("status", ("draft", "active")), name="status"),
        CheckConstraint("planned_income >= 0 AND savings_target >= 0", name="non_negative"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    month: Mapped[date] = mapped_column(Date)
    planned_income: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    savings_target: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(10), server_default=text("'draft'"))
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class BudgetItem(Base):
    __tablename__ = "budget_items"
    __table_args__ = (
        UniqueConstraint("budget_id", "category_id"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )

    id: Mapped[UuidPk]
    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budgets.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)


# "system" = deterministic suggestion engine, "user" = manual edit, "ai" = reserved (LLM).
PROPOSERS = ("ai", "system", "user")


class BudgetAdjustment(Base):
    """A proposed change to an active budget. Applied ONLY after the user approves it;
    approved/rejected rows remain as history."""

    __tablename__ = "budget_adjustments"
    __table_args__ = (
        CheckConstraint(in_list("proposed_by", PROPOSERS), name="proposed_by"),
        CheckConstraint(in_list("status", ("proposed", "approved", "rejected")), name="status"),
    )

    id: Mapped[UuidPk]
    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budgets.id", ondelete="CASCADE"), index=True
    )
    proposed_by: Mapped[str] = mapped_column(String(10))
    # [{"category_id": "...", "old": "4000.00", "new": "3500.00"}, ...]
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), server_default=text("'proposed'"))
    created_at: Mapped[CreatedAt]
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
