import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Money, NonNegativeMoney

WalletType = Literal["cash", "bkash", "nagad", "rocket", "bank", "savings", "other"]


def _clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("name cannot be empty")
    return value


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: WalletType
    opening_balance: Money
    balance: Money
    is_default: bool


class WalletCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    type: WalletType
    opening_balance: NonNegativeMoney = Field(default=0)
    is_default: bool = False

    _name = field_validator("name")(_clean_name)


class WalletUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    type: WalletType | None = None
    # Only `true` is meaningful: it makes this the default (and un-defaults the old one).
    is_default: Literal[True] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


class SetBalance(BaseModel):
    """'My bKash actually has ৳1,240' → creates an adjustment for the difference."""

    model_config = ConfigDict(extra="forbid")

    balance: Money
    note: str | None = Field(default=None, max_length=200)
