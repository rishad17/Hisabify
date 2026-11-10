"""Shared column helpers so every table follows the same conventions."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import DateTime, ForeignKey, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column

# Money is ALWAYS NUMERIC(14,2) in Postgres and Decimal in Python — never float.
# 14 digits with 2 decimals allows up to ৳999,999,999,999.99.
MONEY = Numeric(14, 2, asdecimal=True)
Money = Annotated[Decimal, mapped_column(MONEY)]

UuidPk = Annotated[
    uuid.UUID,
    mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
]

# Every user-owned row points at the profile; deleting a profile deletes all its data.
UserId = Annotated[
    uuid.UUID,
    mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True),
]

CreatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
UpdatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
]


def in_list(column: str, values: tuple[str, ...]) -> str:
    """SQL for a CHECK constraint like  type IN ('a','b').

    We use TEXT + CHECK instead of native Postgres ENUM types: adding a value later is a
    one-line migration instead of an ALTER TYPE dance.
    """
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
