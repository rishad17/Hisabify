import uuid

from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import CreatedAt, UpdatedAt, in_list

LANGUAGES = ("en", "bn")


class Profile(Base):
    """App-level user record. `id` equals the Supabase Auth user id (the JWT `sub`).

    We deliberately do not store email/password here — Supabase Auth owns those.
    """

    __tablename__ = "profiles"
    __table_args__ = (CheckConstraint(in_list("preferred_language", LANGUAGES), name="language"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(60))
    preferred_language: Mapped[str] = mapped_column(String(2), server_default=text("'en'"))
    timezone: Mapped[str] = mapped_column(String(40), server_default=text("'Asia/Dhaka'"))
    # Raw AI prompts are NOT stored unless the user opts in (privacy by default).
    store_ai_text: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
