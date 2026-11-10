"""Month-end spending forecast and budget alerts — simple, explainable statistics.

    projected = spent so far
              + typical daily spending × days remaining
              + unpaid bills this month

"Typical daily spending" = the average of the last 30 complete days, ignoring bill payments
(bills are added separately, on their due dates) and the top 10% of days (one-off spikes
like a laptop shouldn't make every future day look expensive).

This is deliberately NOT machine learning: with weeks of data a transparent average is
more honest than a model. The result always carries a range and a confidence level.
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Transaction
from app.services import ledger, planning
from app.services.budget_engine import taka

ZERO = Decimal("0.00")
WINDOW_DAYS = 30
RANGE = Decimal("0.30")  # ±30% on the not-yet-spent part

Confidence = Literal["low", "medium", "good"]


# ------------------------------------------------------------------ pure maths


def typical_daily(daily_totals: list[Decimal]) -> Decimal:
    """Mean of daily totals after dropping the top 10% of days (needs ≥ 10 days to trim)."""
    if not daily_totals:
        return ZERO
    values = sorted(daily_totals)
    if len(values) >= 10:
        keep = len(values) - max(1, len(values) // 10)
        values = values[:keep]
    return (sum(values, ZERO) / len(values)).quantize(ZERO, rounding=ROUND_HALF_UP)


def confidence_for(history_days: int) -> Confidence:
    if history_days < 14:
        return "low"
    if history_days < 60:
        return "medium"
    return "good"


@dataclass
class Projection:
    projected: Decimal
    low: Decimal
    high: Decimal


def project(
    spent: Decimal, daily: Decimal, remaining_days: int, unpaid_bills: Decimal
) -> Projection:
    future = daily * max(0, remaining_days)
    spread = (future * RANGE).quantize(ZERO)
    base = spent + unpaid_bills
    return Projection(
        projected=(base + future).quantize(ZERO),
        low=(base + future - spread).quantize(ZERO),
        high=(base + future + spread).quantize(ZERO),
    )


# ------------------------------------------------------------------ data


def _daily_totals(
    db: Session, user_id: uuid.UUID, start: date, end: date, category_id=None
) -> list[Decimal]:
    """Expense per day for [start, end), zero-filled, excluding bill payments."""
    t = Transaction
    stmt = (
        select(t.occurred_on, func.sum(t.amount))
        .where(
            t.user_id == user_id,
            t.type == "expense",
            t.voided_at.is_(None),
            t.recurring_bill_id.is_(None),
            t.occurred_on >= start,
            t.occurred_on < end,
        )
        .group_by(t.occurred_on)
    )
    if category_id is not None:
        stmt = stmt.where(t.category_id == category_id)
    by_day = {d: Decimal(s) for d, s in db.execute(stmt).all()}
    days = (end - start).days
    return [by_day.get(start + timedelta(days=i), ZERO) for i in range(days)]


def _first_expense(db: Session, user_id: uuid.UUID) -> date | None:
    return db.scalar(
        select(func.min(Transaction.occurred_on)).where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.voided_at.is_(None),
        )
    )


def month_forecast(db: Session, user_id: uuid.UUID) -> dict:
    today = ledger.today_for(db, user_id)
    month = today.replace(day=1)
    _, month_end = ledger.month_range(month)
    remaining_days = (month_end - today).days - 1  # days AFTER today

    first = _first_expense(db, user_id)
    history_days = (today - first).days if first else 0
    # Window: the last 30 COMPLETE days, but never before the user's first expense.
    window_start = max(today - timedelta(days=WINDOW_DAYS), first or today)
    window = _daily_totals(db, user_id, window_start, today)
    daily = typical_daily(window)

    overview = ledger.month_overview(db, user_id, month)
    spent = overview["expense"]
    bills = [b for b in planning.list_bills(db, user_id, month) if b["active"] and not b["paid"]]
    unpaid = sum((b["amount"] for b in bills), ZERO)
    proj = project(spent, daily, remaining_days, unpaid)
    confidence = confidence_for(history_days)

    # Per budgeted category.
    budget = planning.budget_status(db, user_id, month)
    categories = []
    if budget:
        unpaid_by_cat: dict = {}
        for b in bills:
            cid = b["category"]["id"]
            unpaid_by_cat[cid] = unpaid_by_cat.get(cid, ZERO) + b["amount"]
        for item in budget["items"]:
            cid = item["category"]["id"]
            cat_daily = typical_daily(_daily_totals(db, user_id, window_start, today, cid))
            p = project(item["spent"], cat_daily, remaining_days, unpaid_by_cat.get(cid, ZERO))
            categories.append(
                {
                    "category": item["category"],
                    "budget": item["amount"],
                    "spent": item["spent"],
                    "projected": p.projected,
                    "projected_remaining": item["amount"] - p.projected,
                }
            )

    # Cumulative series for the chart: actual up to today, projected after.
    actual = _daily_totals_all(db, user_id, month, today + timedelta(days=1))
    series, running = [], ZERO
    for i, value in enumerate(actual):
        running += value
        series.append({"date": month + timedelta(days=i), "actual": running, "projected": None})
    if series:
        series[-1]["projected"] = running  # the projection starts where actual ends
    bills_by_day: dict[date, Decimal] = {}
    for b in bills:
        due = max(b["due_date"], today + timedelta(days=1))
        bills_by_day[due] = bills_by_day.get(due, ZERO) + b["amount"]
    projected_running = running
    for i in range(1, remaining_days + 1):
        day = today + timedelta(days=i)
        projected_running += daily + bills_by_day.get(day, ZERO)
        series.append({"date": day, "actual": None, "projected": projected_running.quantize(ZERO)})

    planned_income = budget["planned_income"] if budget else None
    savings = budget["savings_target"] if budget else ZERO
    explanation = [
        f"Spent so far: {taka(spent)}.",
        f"Typical day: {taka(daily)} (last {len(window)} day{'s' if len(window) != 1 else ''}, "
        "excluding bills and unusually big days).",
        f"{remaining_days} day{'s' if remaining_days != 1 else ''} left after today"
        + (f", plus {taka(unpaid)} in unpaid bills." if unpaid else "."),
    ]
    if confidence == "low":
        explanation.append(
            "Less than 2 weeks of history — treat this as a rough estimate; it improves as "
            "you record more."
        )
    return {
        "month": month.strftime("%Y-%m"),
        "spent_so_far": spent,
        "typical_daily": daily,
        "remaining_days": remaining_days,
        "unpaid_bills": unpaid,
        "projected": proj.projected,
        "low": proj.low,
        "high": proj.high,
        "budget_total": budget["total_budget"] if budget else None,
        "planned_income": planned_income,
        "projected_vs_plan": (
            planned_income - savings - proj.projected if planned_income is not None else None
        ),
        "confidence": confidence,
        "history_days": history_days,
        "categories": categories,
        "series": series,
        "explanation": explanation,
    }


def _daily_totals_all(db: Session, user_id: uuid.UUID, start: date, end: date) -> list[Decimal]:
    """Like _daily_totals but INCLUDING bill payments (actual spending for the chart)."""
    t = Transaction
    rows = db.execute(
        select(t.occurred_on, func.sum(t.amount))
        .where(
            t.user_id == user_id,
            t.type == "expense",
            t.voided_at.is_(None),
            t.occurred_on >= start,
            t.occurred_on < end,
        )
        .group_by(t.occurred_on)
    ).all()
    by_day = {d: Decimal(s) for d, s in rows}
    return [by_day.get(start + timedelta(days=i), ZERO) for i in range((end - start).days)]


# ------------------------------------------------------------------ alerts


def budget_alerts(db: Session, user_id: uuid.UUID, forecast: dict | None = None) -> list[dict]:
    """Warnings for the current month's budget, most urgent first."""
    f = forecast or month_forecast(db, user_id)
    days_left = f["remaining_days"] + 1  # including today, as people count it
    alerts = []
    for c in f["categories"]:
        name, budget, spent, projected = (
            c["category"]["name"],
            c["budget"],
            c["spent"],
            c["projected"],
        )
        if budget <= 0:
            continue
        used = int(spent * 100 / budget)
        if spent > budget:
            alerts.append(
                {
                    "category": c["category"],
                    "kind": "over",
                    "severity": "critical",
                    "message": f"{name} is {taka(spent - budget)} over budget.",
                }
            )
        elif used >= 80 and days_left > 1:
            alerts.append(
                {
                    "category": c["category"],
                    "kind": "nearly_used",
                    "severity": "warning",
                    "message": (
                        f"You've used {used}% of your {name} budget, with {days_left} days left."
                    ),
                }
            )
        elif projected > budget:
            alerts.append(
                {
                    "category": c["category"],
                    "kind": "projected_over",
                    "severity": "warning",
                    "message": (
                        f"At your usual pace, {name} will be about {taka(projected - budget)} "
                        "over budget by month end."
                    ),
                }
            )
    order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda a: order[a["severity"]])
    return alerts
