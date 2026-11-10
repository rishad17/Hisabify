import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money
from app.schemas.planning import BudgetDraftOut, CategoryBrief
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


class AIBudgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1000)
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-11"])


class UnderstoodItem(BaseModel):
    category: CategoryBrief
    amount: Money
    fixed: bool


class Understood(BaseModel):
    """Exactly what the AI read from the message — shown so the user can check it."""

    planned_income: Money | None
    savings_target: Money | None
    items: list[UnderstoodItem]


class AIBudgetOut(BaseModel):
    kind: Literal["budget_draft", "clarification"]
    message: str | None
    understood: Understood
    draft: BudgetDraftOut | None
