"""Read-only aggregates for charts. Sums happen in SQL on NUMERIC columns (exact).

Rules shared by every chart:
  * only `expense` and `income` count — transfers and balance corrections never do
  * voided transactions never count
  * gaps (days/months with no activity) are filled with zeros so charts don't skip
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.services import ledger

ZERO = Decimal("0.00")
TOP_CATEGORIES = 7  # the rest fold into "Other" (never more than 8 bars/colours)


def _add_months(d: date, n: int) -> date:
    index = d.year * 12 + d.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


def _active(user_id: uuid.UUID):
    return (
        Transaction.user_id == user_id,
        Transaction.voided_at.is_(None),
        Transaction.type.in_(("expense", "income")),
    )


def _q(value) -> Decimal:
    return Decimal(value or 0).quantize(ZERO)


def category_breakdown(db: Session, user_id: uuid.UUID, month: date) -> dict:
    start, end = ledger.month_range(month)
    rows = db.execute(
        select(Category, func.sum(Transaction.amount).label("total"))
        .join(Category, Category.id == Transaction.category_id)
        .where(
            *_active(user_id),
            Transaction.type == "expense",
            Transaction.occurred_on >= start,
            Transaction.occurred_on < end,
        )
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc(), Category.name)
    ).all()
    total = sum((_q(t) for _, t in rows), ZERO)
    items = [{"category": _ref(c), "amount": _q(t)} for c, t in rows[:TOP_CATEGORIES]]
    if len(rows) > TOP_CATEGORIES:
        other = sum((_q(t) for _, t in rows[TOP_CATEGORIES:]), ZERO)
        items.append({"category": None, "amount": other, "other_count": len(rows) - TOP_CATEGORIES})
    for item in items:
        item["share_percent"] = (
            float((item["amount"] * 100 / total).quantize(Decimal("0.1"))) if total else 0.0
        )
        item.setdefault("other_count", 0)
    return {"month": start.strftime("%Y-%m"), "total": total, "items": items}


def daily(db: Session, user_id: uuid.UUID, month: date) -> dict:
    """One row per day of the month up to today (or the whole month if it's in the past)."""
    start, end = ledger.month_range(month)
    today = ledger.today_for(db, user_id)
    last = min(end - timedelta(days=1), today)
    rows = db.execute(
        select(Transaction.occurred_on, Transaction.type, func.sum(Transaction.amount))
        .where(*_active(user_id), Transaction.occurred_on >= start, Transaction.occurred_on < end)
        .group_by(Transaction.occurred_on, Transaction.type)
    ).all()
    sums: dict[tuple[date, str], Decimal] = {(d, t): _q(s) for d, t, s in rows}

    days = []
    current = start
    while current <= last:
        days.append(
            {
                "date": current,
                "expense": sums.get((current, "expense"), ZERO),
                "income": sums.get((current, "income"), ZERO),
            }
        )
        current += timedelta(days=1)
    spent = sum((d["expense"] for d in days), ZERO)
    average = (spent / len(days)).quantize(ZERO) if days else ZERO
    return {
        "month": start.strftime("%Y-%m"),
        "days": days,
        "total_expense": spent,
        "average_daily_expense": average,
        "days_counted": len(days),
    }


def monthly(db: Session, user_id: uuid.UUID, months: int) -> dict:
    """Income vs expense for the last `months` months, including the current one."""
    this_month = ledger.today_for(db, user_id).replace(day=1)
    first = _add_months(this_month, -(months - 1))
    month_col = func.date_trunc("month", Transaction.occurred_on)
    rows = db.execute(
        select(month_col, Transaction.type, func.sum(Transaction.amount))
        .where(
            *_active(user_id),
            Transaction.occurred_on >= first,
            Transaction.occurred_on < _add_months(this_month, 1),
        )
        .group_by(month_col, Transaction.type)
    ).all()
    sums = {(m.date() if hasattr(m, "date") else m, t): _q(s) for m, t, s in rows}
    result = []
    for i in range(months):
        m = _add_months(first, i)
        income, expense = sums.get((m, "income"), ZERO), sums.get((m, "expense"), ZERO)
        result.append(
            {
                "month": m.strftime("%Y-%m"),
                "income": income,
                "expense": expense,
                "net": income - expense,
                "partial": m == this_month,
            }
        )
    return {"months": result}


def compare(db: Session, user_id: uuid.UUID, month: date) -> dict:
    """Spending by category: this month vs the previous one.

    For the CURRENT month we compare like with like — the same number of days of the
    previous month (e.g. 1–11 Nov vs 1–11 Oct) — otherwise a half-finished month always
    looks cheaper. Past months are compared in full.
    """
    today = ledger.today_for(db, user_id)
    start, end = ledger.month_range(month)
    prev_start = _add_months(start, -1)
    partial = start <= today < end
    if partial:
        day = today.day
        cur_end = today + timedelta(days=1)
        prev_last_day = (start - timedelta(days=1)).day
        prev_end = prev_start + timedelta(days=min(day, prev_last_day))
    else:
        cur_end, prev_end = end, start

    def by_cat(a: date, b: date) -> dict:
        rows = db.execute(
            select(Transaction.category_id, func.sum(Transaction.amount))
            .where(
                *_active(user_id),
                Transaction.type == "expense",
                Transaction.occurred_on >= a,
                Transaction.occurred_on < b,
            )
            .group_by(Transaction.category_id)
        ).all()
        return {cid: _q(s) for cid, s in rows}

    cur, prev = by_cat(start, cur_end), by_cat(prev_start, prev_end)
    cats = {
        c.id: c for c in db.scalars(select(Category).where(Category.id.in_(set(cur) | set(prev))))
    }
    items = [
        {
            "category": _ref(cats[cid]),
            "current": cur.get(cid, ZERO),
            "previous": prev.get(cid, ZERO),
            "change": cur.get(cid, ZERO) - prev.get(cid, ZERO),
        }
        for cid in cats
    ]
    items.sort(key=lambda i: (-max(i["current"], i["previous"]), i["category"]["name"]))
    total_cur = sum(cur.values(), ZERO)
    total_prev = sum(prev.values(), ZERO)

    def day_label(d: date) -> str:
        return f"{d.day} {d:%b}"  # "1 Nov" (portable; %-d isn't supported on Windows)

    return {
        "month": start.strftime("%Y-%m"),
        "partial": partial,
        "current_label": (
            f"{day_label(start)}–{day_label(cur_end - timedelta(days=1))}"
            if partial
            else f"{start:%B %Y}"
        ),
        "previous_label": (
            f"{day_label(prev_start)}–{day_label(prev_end - timedelta(days=1))}"
            if partial
            else f"{prev_start:%B %Y}"
        ),
        "current_total": total_cur,
        "previous_total": total_prev,
        "change": total_cur - total_prev,
        "items": items,
    }


def _ref(c: Category) -> dict:
    return {"id": c.id, "name": c.name, "name_bn": c.name_bn, "icon": c.icon}
