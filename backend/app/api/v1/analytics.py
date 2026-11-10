from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.transactions import MonthParam, parse_month
from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.analytics import (
    CategoryBreakdown,
    DailySeries,
    MonthCompare,
    MonthlySeries,
    Overview,
)
from app.services import analytics, ledger

router = APIRouter()


@router.get("/overview", response_model=Overview)
def overview(
    month: MonthParam = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Dashboard cards. `month` defaults to the current month in the user's timezone."""
    target = parse_month(month) or ledger.today_for(db, user.id).replace(day=1)
    return ledger.month_overview(db, user.id, target)


def _month_or_current(db: Session, user: CurrentUser, month: str | None):
    return parse_month(month) or ledger.today_for(db, user.id).replace(day=1)


@router.get("/category-breakdown", response_model=CategoryBreakdown)
def category_breakdown(
    month: MonthParam = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Expenses by category (top 7 + "Other"). Transfers are never spending."""
    return analytics.category_breakdown(db, user.id, _month_or_current(db, user, month))


@router.get("/daily", response_model=DailySeries)
def daily(
    month: MonthParam = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Day-by-day income and expense, zero-filled, up to today."""
    return analytics.daily(db, user.id, _month_or_current(db, user, month))


@router.get("/monthly", response_model=MonthlySeries)
def monthly(
    months: int = Query(default=6, ge=2, le=24),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Income vs expense for the last N months (current month flagged as partial)."""
    return analytics.monthly(db, user.id, months)


@router.get("/compare", response_model=MonthCompare)
def compare(
    month: MonthParam = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Category spending vs the previous month (same days, if the month isn't over)."""
    return analytics.compare(db, user.id, _month_or_current(db, user, month))
