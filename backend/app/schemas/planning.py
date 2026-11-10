import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Money, NonNegativeMoney, PositiveMoney

MonthStr = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-11"])


def _clean(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("must not be empty")
    return value


class CategoryBrief(BaseModel):
    id: uuid.UUID
    name: str
    name_bn: str | None
    icon: str | None
    is_essential: bool


# ------------------------------------------------------------------ budgets


class StatedAmount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    amount: PositiveMoney
    fixed: bool = False


class BudgetDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str = MonthStr
    planned_income: NonNegativeMoney
    savings_target: NonNegativeMoney = Field(default=0)
    stated: list[StatedAmount] = Field(default_factory=list, max_length=30)
    include_bills: bool = True


class DraftItemOut(BaseModel):
    category: CategoryBrief
    amount: Money
    source: Literal["fixed", "bill", "estimate", "suggested"]


class BudgetDraftOut(BaseModel):
    month: str
    planned_income: Money
    savings_target: Money
    items: list[DraftItemOut]
    allocated: Money
    unallocated: Money
    shortfall: Money
    basis: Literal["history", "typical", "none"]
    explanation: list[str]


class BudgetItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    amount: NonNegativeMoney


class BudgetSaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_income: NonNegativeMoney
    savings_target: NonNegativeMoney = Field(default=0)
    items: list[BudgetItemIn] = Field(max_length=50)
    explanation: str | None = Field(default=None, max_length=2000)


class BudgetItemStatus(BaseModel):
    category: CategoryBrief
    amount: Money
    spent: Money
    remaining: Money
    percent_used: int


class BudgetStatusOut(BaseModel):
    month: str
    planned_income: Money
    savings_target: Money
    explanation: str | None
    items: list[BudgetItemStatus]
    total_budget: Money
    total_spent: Money
    unbudgeted_spent: Money


class BudgetEnvelope(BaseModel):
    """`budget` is null when the month has no budget yet."""

    budget: BudgetStatusOut | None


# ------------------------------------------------------------------ bills


class BillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    amount: PositiveMoney
    category_id: uuid.UUID
    wallet_id: uuid.UUID | None = None
    due_day: int = Field(ge=1, le=31)

    _name = field_validator("name")(_clean)


class BillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    amount: PositiveMoney | None = None
    category_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    active: bool | None = None


class BillOut(BaseModel):
    id: uuid.UUID
    name: str
    amount: Money
    category: CategoryBrief
    wallet_id: uuid.UUID | None
    due_day: int
    due_date: date
    active: bool
    paid: bool
    paid_transaction_id: uuid.UUID | None


class PayBillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet_id: uuid.UUID | None = None
    amount: PositiveMoney | None = None  # defaults to the bill amount
    occurred_on: date | None = None


# ------------------------------------------------------------------ expected income


class ExpectedIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=80)
    amount: PositiveMoney
    expected_on: date

    _source = field_validator("source")(_clean)


class ExpectedUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str | None = Field(default=None, min_length=1, max_length=80)
    amount: PositiveMoney | None = None
    expected_on: date | None = None


class ExpectedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    amount: Money
    expected_on: date
    status: Literal["expected", "received", "cancelled"]
    received_transaction_id: uuid.UUID | None


class ReceiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet_id: uuid.UUID
    category_id: uuid.UUID
    amount: PositiveMoney | None = None
    occurred_on: date | None = None


# ------------------------------------------------------------------ safe to spend


class SafeToSpendOut(BaseModel):
    month: str
    days_left: int
    spendable_balance: Money
    unpaid_bills: Money
    unpaid_bill_count: int
    savings_to_reserve: Money
    essentials_to_reserve: Money
    available: Money
    flexible_budget_left: Money | None
    recommended: Money
    per_day: Money
    expected_income: Money
    available_if_expected_arrives: Money
    has_budget: bool
    confidence: Literal["good", "limited"]
    notes: list[str]


# ------------------------------------------------------------------ purchase simulator


class SimulateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: PositiveMoney
    category_id: uuid.UUID | None = None


class SimulationOut(BaseModel):
    amount: Money
    verdict: Literal[
        "affordable", "likely_affordable", "over_budget", "cuts_into_savings", "not_affordable"
    ]
    available_before: Money
    available_after: Money
    savings_target_left: Money
    savings_shortfall: Money
    commitments_shortfall: Money
    category_name: str | None
    category_remaining_after: Money | None
    flexible_budget_after: Money | None
    affordable_after_expected_income: bool | None
    max_without_touching_savings: Money
    reasons: list[str]
    alternatives: list[str]
