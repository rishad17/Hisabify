from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.transactions import MonthParam, parse_month
from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.analytics import Overview
from app.services import ledger

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
