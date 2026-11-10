import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money


class Overview(BaseModel):
    month: str  # "2026-11"
    total_balance: Money  # all active wallets, right now
    income: Money  # this month; transfers/adjustments excluded
    expense: Money  # this month; transfers/adjustments excluded
    net: Money  # income - expense
    transaction_count: int


# ------------------------------------------------------------------ charts


class ChartCategory(BaseModel):
    id: uuid.UUID
    name: str
    name_bn: str | None
    icon: str | None


class BreakdownItem(BaseModel):
    category: ChartCategory | None  # None = "Other" (folded small categories)
    amount: Money
    share_percent: float
    other_count: int


class CategoryBreakdown(BaseModel):
    month: str
    total: Money
    items: list[BreakdownItem]


class DayPoint(BaseModel):
    date: date
    expense: Money
    income: Money


class DailySeries(BaseModel):
    month: str
    days: list[DayPoint]
    total_expense: Money
    average_daily_expense: Money
    days_counted: int


class MonthPoint(BaseModel):
    month: str
    income: Money
    expense: Money
    net: Money
    partial: bool  # the current, unfinished month


class MonthlySeries(BaseModel):
    months: list[MonthPoint]


class CompareItem(BaseModel):
    category: ChartCategory
    current: Money
    previous: Money
    change: Money


class MonthCompare(BaseModel):
    month: str
    partial: bool
    current_label: str
    previous_label: str
    current_total: Money
    previous_total: Money
    change: Money
    items: list[CompareItem]
