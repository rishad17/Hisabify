from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import CreatedAt, UserId, UuidPk, in_list

CATEGORY_KINDS = ("expense", "income")


class Category(Base):
    """Per-user categories (seeded with defaults on first login, user can add more).

    `name_bn` lets the UI and AI show Bangla names; `is_essential` marks spending that
    safe-to-spend must reserve (rent, bills, groceries…)."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "name"),
        CheckConstraint(in_list("kind", CATEGORY_KINDS), name="kind"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    name: Mapped[str] = mapped_column(String(50))
    name_bn: Mapped[str | None] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(10))
    is_essential: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    icon: Mapped[str | None] = mapped_column(String(40))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
