"""Budgets, bills, expected income and safe-to-spend."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.orm import Session

from app.api.v1.transactions import IdempotencyKey, parse_month
from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.planning import (
    AdjustmentOut,
    AlertOut,
    BillIn,
    BillOut,
    BillUpdate,
    BudgetDraftIn,
    BudgetDraftOut,
    BudgetEnvelope,
    BudgetSaveIn,
    ExpectedIn,
    ExpectedOut,
    ExpectedUpdate,
    ForecastOut,
    PayBillIn,
    ReceiveIn,
    SafeToSpendOut,
    SimulateIn,
    SimulationOut,
    SuggestOut,
)
from app.schemas.transaction import TransactionOut
from app.services import adjustments, forecast, ledger, planning, simulator

budgets = APIRouter()
bills = APIRouter()
expected = APIRouter()
plan = APIRouter()

Month = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-11"])


def _month(value: str) -> date:
    parsed = parse_month(value)
    assert parsed is not None
    return parsed


# ------------------------------------------------------------------ budgets


@budgets.post("/draft", response_model=BudgetDraftOut)
def draft(
    body: BudgetDraftIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Calculate a budget (deterministic engine). Nothing is saved."""
    return planning.draft_budget(
        db,
        user.id,
        planning.DraftInput(
            month=_month(body.month),
            planned_income=body.planned_income,
            savings_target=body.savings_target,
            stated=[(s.category_id, s.amount, s.fixed) for s in body.stated],
            include_bills=body.include_bills,
        ),
    )


@budgets.get("/{month}", response_model=BudgetEnvelope)
def get_budget(
    month: str = Month,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """The month's budget with spending per category, or {"budget": null}."""
    return {"budget": planning.budget_status(db, user.id, _month(month))}


@budgets.put("/{month}", response_model=BudgetEnvelope)
def save_budget(
    body: BudgetSaveIn,
    month: str = Month,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Save the budget the user reviewed and confirmed (replaces any existing one)."""
    m = _month(month)
    planning.save_budget(
        db,
        user.id,
        m,
        planned_income=body.planned_income,
        savings_target=body.savings_target,
        items=[(i.category_id, i.amount) for i in body.items],
        explanation=body.explanation,
    )
    return {"budget": planning.budget_status(db, user.id, m)}


@budgets.delete("/{month}", status_code=204)
def delete_budget(
    month: str = Month,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    planning.delete_budget(db, user.id, _month(month))
    return Response(status_code=204)


# ------------------------------------------------------------------ bills


def _this_month(db: Session, user: CurrentUser) -> date:
    return ledger.today_for(db, user.id).replace(day=1)


def _bill_out(db: Session, user: CurrentUser, bill_id: uuid.UUID) -> dict:
    return next(
        b for b in planning.list_bills(db, user.id, _this_month(db, user)) if b["id"] == bill_id
    )


@bills.get("", response_model=list[BillOut])
def list_bills(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """All bills with paid/unpaid status for the current month."""
    return planning.list_bills(db, user.id, _this_month(db, user))


@bills.post("", response_model=BillOut, status_code=201)
def create_bill(
    body: BillIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    bill = planning.create_bill(db, user.id, **body.model_dump())
    return _bill_out(db, user, bill.id)


@bills.patch("/{bill_id}", response_model=BillOut)
def update_bill(
    bill_id: uuid.UUID,
    body: BillUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    planning.update_bill(db, user.id, bill_id, body.model_dump(exclude_unset=True))
    return _bill_out(db, user, bill_id)


@bills.delete("/{bill_id}", status_code=204)
def delete_bill(
    bill_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    planning.delete_bill(db, user.id, bill_id)
    return Response(status_code=204)


@bills.post("/{bill_id}/pay", response_model=TransactionOut, status_code=201)
def pay_bill(
    bill_id: uuid.UUID,
    body: PayBillIn,
    idempotency_key: IdempotencyKey,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Record this month's payment as an expense linked to the bill."""
    tx = planning.pay_bill(
        db,
        user.id,
        bill_id,
        wallet_id=body.wallet_id,
        amount=body.amount,
        occurred_on=body.occurred_on,
        idempotency_key=idempotency_key,
    )
    return ledger.load_out(db, user.id, [tx.id])[0]


# ------------------------------------------------------------------ expected income


@expected.get("", response_model=list[ExpectedOut])
def list_expected(
    include_closed: bool = False,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    return planning.list_expected(db, user.id, include_closed)


@expected.post("", response_model=ExpectedOut, status_code=201)
def create_expected(
    body: ExpectedIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    return planning.create_expected(db, user.id, **body.model_dump())


@expected.patch("/{eid}", response_model=ExpectedOut)
def update_expected(
    eid: uuid.UUID,
    body: ExpectedUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return planning.update_expected(db, user.id, eid, body.model_dump(exclude_unset=True))


@expected.post("/{eid}/cancel", response_model=ExpectedOut)
def cancel_expected(
    eid: uuid.UUID, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    return planning.cancel_expected(db, user.id, eid)


@expected.post("/{eid}/receive", response_model=ExpectedOut)
def receive_expected(
    eid: uuid.UUID,
    body: ReceiveIn,
    idempotency_key: IdempotencyKey,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The money arrived: records a real income transaction and marks this as received."""
    row, _ = planning.receive_expected(
        db,
        user.id,
        eid,
        wallet_id=body.wallet_id,
        category_id=body.category_id,
        amount=body.amount,
        occurred_on=body.occurred_on,
        idempotency_key=idempotency_key,
    )
    return row


# ------------------------------------------------------------------ safe to spend


@plan.get("/safe-to-spend", response_model=SafeToSpendOut)
def safe_to_spend(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Commitment-aware: what you can spend after reserving bills, savings and essentials."""
    return planning.safe_to_spend(db, user.id)


@plan.post("/simulate", response_model=SimulationOut)
def simulate(
    body: SimulateIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """What-if purchase check. Read-only: nothing is recorded."""
    return simulator.simulate_purchase(db, user.id, body.amount, body.category_id).__dict__


# ------------------------------------------------------------------ forecast & adaptive budget


@plan.get("/forecast", response_model=ForecastOut)
def get_forecast(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Projected month-end spending (an estimate with a range and confidence level)."""
    return forecast.month_forecast(db, user.id)


@plan.get("/alerts", response_model=list[AlertOut])
def get_alerts(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """Budget warnings for this month (over, nearly used up, on track to overshoot)."""
    return forecast.budget_alerts(db, user.id)


@budgets.post("/suggest-adjustment", response_model=SuggestOut)
def suggest_adjustment(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Propose moving budget between categories. Changes NOTHING until approved."""
    suggestion, message = adjustments.create_suggestion(db, user.id)
    return {"suggestion": suggestion, "message": message}


@budgets.get("/{month}/adjustments", response_model=list[AdjustmentOut])
def adjustment_history(
    month: str = Month,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Every proposed, approved and rejected change to this month's budget."""
    return adjustments.history(db, user.id, _month(month))


@budgets.post("/adjustments/{adj_id}/approve", response_model=AdjustmentOut)
def approve_adjustment(
    adj_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return adjustments.decide(db, user.id, adj_id, approve=True)


@budgets.post("/adjustments/{adj_id}/reject", response_model=AdjustmentOut)
def reject_adjustment(
    adj_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return adjustments.decide(db, user.id, adj_id, approve=False)
