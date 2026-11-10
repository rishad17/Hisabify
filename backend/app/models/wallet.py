from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import MONEY, CreatedAt, UserId, UuidPk, in_list

WALLET_TYPES = ("cash", "bkash", "nagad", "rocket", "bank", "savings", "other")


class Wallet(Base):
    """A place money is kept. The balance is NOT stored — it is derived from
    opening_balance + all non-voided transactions (see services/ledger.py, Phase 2),
    so it can never drift out of sync."""

    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint(in_list("type", WALLET_TYPES), name="type"),
        # At most one default wallet per user (partial unique index).
        Index(
            "uq_wallets_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    name: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(20))
    opening_balance: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
