import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money
from app.schemas.transaction import CategoryRef


class AIMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1000)
    source: Literal["text", "voice"] = "text"


class DraftIssue(BaseModel):
    code: str
    message: str
    severity: Literal["warning", "error"]


class DraftItemOut(BaseModel):
    type: Literal["expense", "income", "transfer"]
    amount: Money
    description: str
    category: CategoryRef | None
    wallet_id: uuid.UUID | None
    wallet_name: str | None
    to_wallet_id: uuid.UUID | None
    to_wallet_name: str | None
    occurred_on: date
    wallet_defaulted: bool
    issues: list[DraftIssue]


class PlannedOut(BaseModel):
    description: str
    amount: Money | None
    date: date | None


class DraftOut(BaseModel):
    # Use this as the Idempotency-Key when saving the confirmed draft.
    draft_id: str
    source: Literal["text", "voice"]
    items: list[DraftItemOut]
    planned: list[PlannedOut]
    expense_total: Money
    income_total: Money


class AIMessageOut(BaseModel):
    """What the assistant replies.

    kind:
      transaction_draft — items to preview/confirm (may also carry clarifications)
      clarification     — nothing to record yet; `message` asks the user something
      unsupported       — understood, but this feature isn't built yet (e.g. questions)
    """

    kind: Literal["transaction_draft", "clarification", "unsupported"]
    message: str | None = None
    clarifications: list[str] = []
    draft: DraftOut | None = None


class TranscriptOut(BaseModel):
    text: str
    language: Literal["bn", "en", "mixed", "unknown"]
    provider: str
