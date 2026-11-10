import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Money, PositiveMoney

TransactionType = Literal["expense", "income", "transfer", "adjustment"]
CreatableType = Literal["expense", "income", "transfer"]  # adjustments only via set-balance
Source = Literal["manual", "text", "voice"]


def _clean_description(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


class TransactionIn(BaseModel):
    """One transaction inside a batch (manual form, or a confirmed AI draft later)."""

    model_config = ConfigDict(extra="forbid")

    type: CreatableType
    amount: PositiveMoney
    wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=200)
    occurred_on: date | None = None  # defaults to "today" in the user's timezone

    _desc = field_validator("description")(_clean_description)


class TransactionBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source = "manual"
    items: list[TransactionIn] = Field(min_length=1, max_length=20)


class TransactionUpdate(BaseModel):
    """PATCH body. The merged result is validated with the same rules as creation."""

    model_config = ConfigDict(extra="forbid")

    type: CreatableType | None = None
    amount: PositiveMoney | None = None
    wallet_id: uuid.UUID | None = None
    to_wallet_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=200)
    occurred_on: date | None = None

    _desc = field_validator("description")(_clean_description)

    @field_validator("type", "amount", "wallet_id", "occurred_on", mode="before")
    @classmethod
    def _required_not_null(cls, value: object) -> object:
        # Omit a field to keep it; explicit null is only allowed for optional fields
        # (to_wallet_id, category_id, description).
        if value is None:
            raise ValueError("may be omitted but not null")
        return value


class CategoryRef(BaseModel):
    id: uuid.UUID
    name: str
    name_bn: str | None
    icon: str | None


class TransactionOut(BaseModel):
    id: uuid.UUID
    type: TransactionType
    amount: Money
    wallet_id: uuid.UUID
    wallet_name: str
    to_wallet_id: uuid.UUID | None
    to_wallet_name: str | None
    category: CategoryRef | None
    description: str | None
    occurred_on: date
    source: Source
    voided: bool
    created_at: datetime


class TransactionBatchOut(BaseModel):
    items: list[TransactionOut]
    # True when this Idempotency-Key was already used: nothing new was saved.
    replayed: bool


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int
