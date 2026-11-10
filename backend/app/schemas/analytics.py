from pydantic import BaseModel

from app.schemas.common import Money


class Overview(BaseModel):
    month: str  # "2026-11"
    total_balance: Money  # all active wallets, right now
    income: Money  # this month; transfers/adjustments excluded
    expense: Money  # this month; transfers/adjustments excluded
    net: Money  # income - expense
    transaction_count: int
