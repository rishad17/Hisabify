import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str | None
    preferred_language: Literal["en", "bn"]
    timezone: str
    store_ai_text: bool


class MeOut(BaseModel):
    profile: ProfileOut
    email: str | None
    default_wallet_name: str | None
    category_count: int
    is_new_user: bool


class ProfileUpdate(BaseModel):
    """PATCH body — every field optional; only provided fields change."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=60)
    preferred_language: Literal["en", "bn"] | None = None
    store_ai_text: bool | None = None

    @field_validator("display_name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())  # trim + collapse internal whitespace
        return value or None

    @field_validator("preferred_language", "store_ai_text", mode="before")
    @classmethod
    def _not_null(cls, value: object) -> object:
        # These may be omitted, but sending an explicit null makes no sense.
        if value is None:
            raise ValueError("may be omitted but not null")
        return value
