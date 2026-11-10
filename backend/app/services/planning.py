"""Budgets, commitments (bills, expected income) and commitment-aware safe-to-spend.

All arithmetic is Decimal; every query is scoped to the user.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Budget,
    BudgetItem,
    Category,
    ExpectedIncome,
    RecurringBill,
    Transaction,
    Wallet,
)
from app.schemas.transaction import TransactionIn
from app.services import ledger
from app.services.budget_engine import Bill, EngineCategory, Stated, plan_budget, taka

ZERO = Decimal("0.00")


def _not_found(what: str) -> AppError:
    return AppError(f"{what}_not_found", f"{what.replace('_', ' ').capitalize()} not found.", 404)


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    index = d.year * 12 + d.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


def _days_in_month(month: date) -> int:
    return (_add_months(month, 1) - month).days


# ---------------------------------------------------------------- spending reads


def spent_by_category(db: Session, user_id: uuid.UUID, month: date) -> dict[uuid.UUID, Decimal]:
    start, end = ledger.month_range(month)
    rows = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.voided_at.is_(None),
            Transaction.occurred_on >= start,
            Transaction.occurred_on < end,
        )
        .group_by(Transaction.category_id)
    ).all()
    return {cid: Decimal(total).quantize(ZERO) for cid, total in rows}


def history_average(db: Session, user_id: uuid.UUID, month: date) -> dict[uuid.UUID, Decimal]:
    """Average monthly spend per category over the previous (up to) 3 months that have data."""
    start = _add_months(month, -3)
    rows = db.execute(
        select(
            Transaction.category_id,
            func.sum(Transaction.amount),
            func.count(func.distinct(func.date_trunc("month", Transaction.occurred_on))),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.voided_at.is_(None),
            Transaction.occurred_on >= start,
            Transaction.occurred_on < month,
        )
        .group_by(Transaction.category_id)
    ).all()
    months_with_data = db.scalar(
        select(func.count(func.distinct(func.date_trunc("month", Transaction.occurred_on)))).where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.voided_at.is_(None),
            Transaction.occurred_on >= start,
            Transaction.occurred_on < month,
        )
    )
    if not months_with_data:
        return {}
    return {cid: (Decimal(total) / months_with_data).quantize(ZERO) for cid, total, _ in rows}


def _expense_categories(db: Session, user_id: uuid.UUID) -> list[Category]:
    return list(
        db.scalars(
            select(Category).where(
                Category.user_id == user_id,
                Category.kind == "expense",
                Category.archived_at.is_(None),
            )
        )
    )


def _check_expense_category(db: Session, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    cat = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
    if cat is None:
        raise _not_found("category")
    if cat.kind != "expense":
        raise AppError("category_kind_mismatch", f'"{cat.name}" is not an expense category.', 422)
    return cat


# ---------------------------------------------------------------- budget draft


@dataclass
class DraftInput:
    month: date
    planned_income: Decimal
    savings_target: Decimal
    stated: list[tuple[uuid.UUID, Decimal, bool]]  # (category_id, amount, is_fixed)
    include_bills: bool = True


def draft_budget(db: Session, user_id: uuid.UUID, data: DraftInput) -> dict:
    categories = _expense_categories(db, user_id)
    for cid, _, _ in data.stated:
        _check_expense_category(db, user_id, cid)
    bills = (
        [
            Bill(b.category_id, b.amount, b.name)
            for b in db.scalars(
                select(RecurringBill).where(RecurringBill.user_id == user_id, RecurringBill.active)
            )
        ]
        if data.include_bills
        else []
    )
    plan = plan_budget(
        planned_income=data.planned_income,
        savings_target=data.savings_target,
        categories=[EngineCategory(c.id, c.name, c.is_essential) for c in categories],
        stated=[Stated(cid, amount, fixed) for cid, amount, fixed in data.stated],
        bills=bills,
        history=history_average(db, user_id, data.month),
    )
    by_id = {c.id: c for c in categories}
    return {
        "month": data.month.strftime("%Y-%m"),
        "planned_income": plan.planned_income,
        "savings_target": plan.savings_target,
        "items": [
            {
                "category": _cat_ref(by_id[i.category_id]),
                "amount": i.amount,
                "source": i.source,
            }
            for i in plan.items
        ],
        "allocated": plan.allocated,
        "unallocated": plan.planned_income - plan.savings_target - plan.allocated,
        "shortfall": plan.shortfall,
        "basis": plan.basis,
        "explanation": plan.explanation,
    }


def _cat_ref(c: Category) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "name_bn": c.name_bn,
        "icon": c.icon,
        "is_essential": c.is_essential,
    }


# ---------------------------------------------------------------- saved budgets


def save_budget(
    db: Session,
    user_id: uuid.UUID,
    month: date,
    *,
    planned_income: Decimal,
    savings_target: Decimal,
    items: list[tuple[uuid.UUID, Decimal]],
    explanation: str | None,
) -> Budget:
    """Create or replace the month's budget (the user confirmed it in the editor)."""
    seen: set[uuid.UUID] = set()
    for cid, amount in items:
        _check_expense_category(db, user_id, cid)
        if cid in seen:
            raise AppError("duplicate_category", "Each category can appear only once.", 422)
        if amount < 0:
            raise AppError("negative_amount", "Budget amounts can't be negative.", 422)
        seen.add(cid)

    budget = db.scalar(select(Budget).where(Budget.user_id == user_id, Budget.month == month))
    if budget is None:
        budget = Budget(user_id=user_id, month=month)
        db.add(budget)
    budget.planned_income = planned_income
    budget.savings_target = savings_target
    budget.status = "active"
    budget.ai_explanation = explanation
    db.flush()
    db.execute(delete(BudgetItem).where(BudgetItem.budget_id == budget.id))
    db.add_all(
        BudgetItem(budget_id=budget.id, category_id=cid, amount=amount)
        for cid, amount in items
        if amount > 0
    )
    db.commit()
    return budget


def delete_budget(db: Session, user_id: uuid.UUID, month: date) -> None:
    budget = db.scalar(select(Budget).where(Budget.user_id == user_id, Budget.month == month))
    if budget is None:
        raise _not_found("budget")
    db.delete(budget)
    db.commit()


def budget_status(db: Session, user_id: uuid.UUID, month: date) -> dict | None:
    """The saved budget with actual spending per category ('budget vs actual')."""
    budget = db.scalar(select(Budget).where(Budget.user_id == user_id, Budget.month == month))
    if budget is None:
        return None
    spent = spent_by_category(db, user_id, month)
    rows = db.execute(
        select(BudgetItem, Category)
        .join(Category, Category.id == BudgetItem.category_id)
        .where(BudgetItem.budget_id == budget.id)
        .order_by(BudgetItem.amount.desc())
    ).all()
    budgeted_ids = {item.category_id for item, _ in rows}
    items = []
    for item, cat in rows:
        s = spent.get(cat.id, ZERO)
        items.append(
            {
                "category": _cat_ref(cat),
                "amount": item.amount,
                "spent": s,
                "remaining": item.amount - s,
                "percent_used": int(s * 100 / item.amount) if item.amount > 0 else 0,
            }
        )
    unbudgeted = sum((v for k, v in spent.items() if k not in budgeted_ids), ZERO)
    total_budget = sum((i["amount"] for i in items), ZERO)
    total_spent = sum(spent.values(), ZERO)
    return {
        "month": month.strftime("%Y-%m"),
        "planned_income": budget.planned_income,
        "savings_target": budget.savings_target,
        "explanation": budget.ai_explanation,
        "items": items,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "unbudgeted_spent": unbudgeted,
    }


# ---------------------------------------------------------------- recurring bills


def _owned_bill(db: Session, user_id: uuid.UUID, bill_id: uuid.UUID) -> RecurringBill:
    bill = db.scalar(
        select(RecurringBill).where(RecurringBill.id == bill_id, RecurringBill.user_id == user_id)
    )
    if bill is None:
        raise _not_found("bill")
    return bill


def bill_payments(db: Session, user_id: uuid.UUID, month: date) -> dict[uuid.UUID, Transaction]:
    start, end = ledger.month_range(month)
    txs = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.recurring_bill_id.is_not(None),
            Transaction.voided_at.is_(None),
            Transaction.occurred_on >= start,
            Transaction.occurred_on < end,
        )
    )
    return {t.recurring_bill_id: t for t in txs}


def list_bills(db: Session, user_id: uuid.UUID, month: date) -> list[dict]:
    paid = bill_payments(db, user_id, month)
    rows = db.execute(
        select(RecurringBill, Category)
        .join(Category, Category.id == RecurringBill.category_id)
        .where(RecurringBill.user_id == user_id)
        .order_by(RecurringBill.active.desc(), RecurringBill.due_day, RecurringBill.name)
    ).all()
    last_day = _days_in_month(month)
    return [
        {
            "id": b.id,
            "name": b.name,
            "amount": b.amount,
            "category": _cat_ref(c),
            "wallet_id": b.wallet_id,
            "due_day": b.due_day,
            "due_date": month.replace(day=min(b.due_day, last_day)),
            "active": b.active,
            "paid": b.id in paid,
            "paid_transaction_id": paid[b.id].id if b.id in paid else None,
        }
        for b, c in rows
    ]


def create_bill(db: Session, user_id: uuid.UUID, **fields) -> RecurringBill:
    _check_expense_category(db, user_id, fields["category_id"])
    if fields.get("wallet_id"):
        ledger._owned_wallet(db, user_id, fields["wallet_id"])
    bill = RecurringBill(user_id=user_id, **fields)
    db.add(bill)
    db.commit()
    return bill


def update_bill(db: Session, user_id: uuid.UUID, bill_id: uuid.UUID, changes: dict) -> None:
    bill = _owned_bill(db, user_id, bill_id)
    if "category_id" in changes:
        _check_expense_category(db, user_id, changes["category_id"])
    if changes.get("wallet_id"):
        ledger._owned_wallet(db, user_id, changes["wallet_id"])
    for k, v in changes.items():
        setattr(bill, k, v)
    db.commit()


def delete_bill(db: Session, user_id: uuid.UUID, bill_id: uuid.UUID) -> None:
    """Past payments keep their history (recurring_bill_id becomes NULL)."""
    db.delete(_owned_bill(db, user_id, bill_id))
    db.commit()


def pay_bill(
    db: Session,
    user_id: uuid.UUID,
    bill_id: uuid.UUID,
    *,
    wallet_id: uuid.UUID | None,
    amount: Decimal | None,
    occurred_on: date | None,
    idempotency_key: str,
) -> Transaction:
    """Record this month's payment as a normal expense linked to the bill."""
    bill = _owned_bill(db, user_id, bill_id)
    # A retried request (same key) returns the original payment instead of an error.
    replay = ledger._rows_for_key(db, user_id, idempotency_key)
    if replay:
        return replay[0]
    today = ledger.today_for(db, user_id)
    when = occurred_on or today
    if bill_payments(db, user_id, _month_start(when)).get(bill.id):
        raise AppError("bill_already_paid", f'"{bill.name}" is already paid for this month.', 409)
    wallet = wallet_id or bill.wallet_id or _default_wallet_id(db, user_id)

    item = TransactionIn(
        type="expense",
        amount=amount or bill.amount,
        wallet_id=wallet,
        category_id=bill.category_id,
        description=bill.name,
        occurred_on=when,
    )
    rows, _ = ledger.create_batch(
        db, user_id, [item], idempotency_key=idempotency_key, source="manual"
    )
    tx = rows[0]
    if tx.recurring_bill_id is None:
        tx.recurring_bill_id = bill.id
        db.commit()
    return tx


def _default_wallet_id(db: Session, user_id: uuid.UUID) -> uuid.UUID:
    wid = db.scalar(
        select(Wallet.id).where(
            Wallet.user_id == user_id, Wallet.is_default, Wallet.archived_at.is_(None)
        )
    )
    if wid is None:
        raise AppError("wallet_missing", "Choose a wallet.", 422)
    return wid


# ---------------------------------------------------------------- expected income


def _owned_expected(db: Session, user_id: uuid.UUID, eid: uuid.UUID) -> ExpectedIncome:
    row = db.scalar(
        select(ExpectedIncome).where(ExpectedIncome.id == eid, ExpectedIncome.user_id == user_id)
    )
    if row is None:
        raise _not_found("expected_income")
    return row


def list_expected(db: Session, user_id: uuid.UUID, include_closed: bool) -> list[ExpectedIncome]:
    stmt = select(ExpectedIncome).where(ExpectedIncome.user_id == user_id)
    if not include_closed:
        stmt = stmt.where(ExpectedIncome.status == "expected")
    order = case((ExpectedIncome.status == "expected", 0), else_=1)
    return list(db.scalars(stmt.order_by(order, ExpectedIncome.expected_on)))


def create_expected(db: Session, user_id: uuid.UUID, **fields) -> ExpectedIncome:
    row = ExpectedIncome(user_id=user_id, **fields)
    db.add(row)
    db.commit()
    return row


def update_expected(
    db: Session, user_id: uuid.UUID, eid: uuid.UUID, changes: dict
) -> ExpectedIncome:
    row = _owned_expected(db, user_id, eid)
    if row.status != "expected":
        raise AppError(
            "expected_income_closed", "This income is already received or cancelled.", 422
        )
    for k, v in changes.items():
        setattr(row, k, v)
    db.commit()
    return row


def cancel_expected(db: Session, user_id: uuid.UUID, eid: uuid.UUID) -> ExpectedIncome:
    return update_expected(db, user_id, eid, {"status": "cancelled"})


def receive_expected(
    db: Session,
    user_id: uuid.UUID,
    eid: uuid.UUID,
    *,
    wallet_id: uuid.UUID,
    category_id: uuid.UUID,
    amount: Decimal | None,
    occurred_on: date | None,
    idempotency_key: str,
) -> tuple[ExpectedIncome, Transaction]:
    """The money arrived: record a real income transaction and link it."""
    row = _owned_expected(db, user_id, eid)
    if row.status == "received" and row.received_transaction_id:
        tx = db.get(Transaction, row.received_transaction_id)
        if tx is not None:
            return row, tx  # retry of the same action
    if row.status != "expected":
        raise AppError("expected_income_closed", "This income was cancelled.", 422)

    item = TransactionIn(
        type="income",
        amount=amount or row.amount,
        wallet_id=wallet_id,
        category_id=category_id,
        description=row.source,
        occurred_on=occurred_on,
    )
    rows, _ = ledger.create_batch(
        db, user_id, [item], idempotency_key=idempotency_key, source="manual"
    )
    row.status = "received"
    row.received_transaction_id = rows[0].id
    db.commit()
    return row, rows[0]


# ---------------------------------------------------------------- safe to spend


def safe_to_spend(db: Session, user_id: uuid.UUID) -> dict:
    """How much can I spend for the rest of this month without hurting commitments?

        available  = money in non-savings wallets
                   − unpaid bills this month
                   − savings target not yet moved to savings wallets
                   − remaining budget for ESSENTIAL categories (minus bills already counted)
        per day    = available ÷ days left (incl. today)

    Expected (not yet received) income is reported separately, never counted as money.
    """
    today = ledger.today_for(db, user_id)
    month = _month_start(today)
    start, end = ledger.month_range(month)
    days_left = (end - today).days

    wallets = ledger.list_wallets(db, user_id)
    spendable = sum((w.balance for w in wallets if w.wallet.type != "savings"), ZERO)
    savings_wallet_ids = [w.wallet.id for w in wallets if w.wallet.type == "savings"]

    bills = [b for b in list_bills(db, user_id, month) if b["active"] and not b["paid"]]
    unpaid_bills = sum((b["amount"] for b in bills), ZERO)
    unpaid_by_cat: dict[uuid.UUID, Decimal] = {}
    for b in bills:
        unpaid_by_cat[b["category"]["id"]] = (
            unpaid_by_cat.get(b["category"]["id"], ZERO) + b["amount"]
        )

    budget = budget_status(db, user_id, month)
    notes: list[str] = []
    savings_left = ZERO
    essential_left = ZERO
    flexible_budget_left: Decimal | None = None
    if budget is None:
        notes.append("No budget for this month — savings and essentials aren't reserved.")
    else:
        moved_to_savings = ZERO
        if savings_wallet_ids:
            moved_to_savings = (
                db.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                        Transaction.user_id == user_id,
                        Transaction.type == "transfer",
                        Transaction.voided_at.is_(None),
                        Transaction.to_wallet_id.in_(savings_wallet_ids),
                        Transaction.occurred_on >= start,
                        Transaction.occurred_on < end,
                    )
                )
                or ZERO
            )
        savings_left = max(ZERO, budget["savings_target"] - Decimal(moved_to_savings))
        flexible_budget_left = ZERO
        for item in budget["items"]:
            remaining = max(ZERO, item["remaining"])
            if item["category"]["is_essential"]:
                # Don't reserve twice: an unpaid rent bill already covers the rent budget.
                essential_left += max(
                    ZERO, remaining - unpaid_by_cat.get(item["category"]["id"], ZERO)
                )
            else:
                flexible_budget_left += remaining
    if not bills and not any(b["active"] for b in list_bills(db, user_id, month)):
        notes.append("No recurring bills recorded — add rent/bills for a more accurate number.")

    available = spendable - unpaid_bills - savings_left - essential_left
    expected = [e for e in list_expected(db, user_id, include_closed=False) if e.expected_on < end]
    expected_total = sum((e.amount for e in expected), ZERO)

    def per_day(amount: Decimal) -> Decimal:
        if amount <= 0 or days_left <= 0:
            return ZERO
        return (amount / days_left).quantize(Decimal("1"), rounding=ROUND_DOWN).quantize(ZERO)

    # Recommended = what both your money AND your flexible budget allow.
    recommended = available
    if flexible_budget_left is not None:
        recommended = min(available, flexible_budget_left)
    recommended = max(ZERO, recommended)

    if available < 0:
        notes.insert(0, f"Your commitments exceed your money by {taka(-available)}.")
    return {
        "month": month.strftime("%Y-%m"),
        "days_left": days_left,
        "spendable_balance": spendable,
        "unpaid_bills": unpaid_bills,
        "unpaid_bill_count": len(bills),
        "savings_to_reserve": savings_left,
        "essentials_to_reserve": essential_left,
        "available": available,
        "flexible_budget_left": flexible_budget_left,
        "recommended": recommended,
        "per_day": per_day(recommended),
        "expected_income": expected_total,
        "available_if_expected_arrives": available + expected_total,
        "has_budget": budget is not None,
        "confidence": "good" if budget is not None and not notes else "limited",
        "notes": notes,
    }
