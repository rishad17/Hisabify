from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import CreatedAt, UserId, UuidPk, in_list


class AIInteraction(Base):
    """Minimal AI usage log: for debugging, cost tracking and rate limits.

    The user's actual message is stored ONLY if they opted in (profiles.store_ai_text).
    """

    __tablename__ = "ai_interactions"
    __table_args__ = (
        CheckConstraint(in_list("status", ("ok", "clarify", "error")), name="status"),
        Index("ix_ai_interactions_user_created", "user_id", "created_at"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[UserId]
    intent: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(10))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    input_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
