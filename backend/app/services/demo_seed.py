"""Realistic demo data (≈3 months) for a portfolio demo account.

A university student who also freelances: family allowance via bKash, tuition income,
occasional freelance payments, daily cha/rickshaw/lunch, weekly bazar, rent and internet
bills, a budget for this month and an expected freelance payment.

Everything goes through the normal services (same validation as real users) and is
deterministic (fixed random seed), so the demo looks the same every time.
"""

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.schemas.transaction import TransactionIn
from app.services import ledger, planning
from app.services.onboarding import ensure_profile


class DemoSeedError(Exception):
    pass


def _month_start(d: date, back: int) -> date:
    index = d.year * 12 + d.month - 1 - back
    return date(index // 12, index % 12 + 1, 1)


def seed_demo(db: Session, user_id: uuid.UUID, *, today: date | None = None) -> dict:
    ensure_profile(db, user_id)
    if db.scalar(select(func.count()).where(Transaction.user_id == user_id)):
        raise DemoSeedError("This account already has transactions. Use --reset to wipe first.")

    today = today or ledger.today_for(db, user_id)
    rng = random.Random(42)
    cat = {c.name: c.id for c in db.scalars(select(Category).where(Category.user_id == user_id))}
    cash = next(w.wallet.id for w in ledger.list_wallets(db, user_id) if w.wallet.is_default)
    bkash = ledger.create_wallet(
        db, user_id, name="bKash", type="bkash", opening_balance=Decimal("1500"), is_default=False
    ).id
    bank = ledger.create_wallet(
        db, user_id, name="Bank", type="bank", opening_balance=Decimal("12000"), is_default=False
    ).id

    count = 0

    def add(items: list[TransactionIn]) -> None:
        nonlocal count
        ledger.create_batch(db, user_id, items, idempotency_key=uuid.uuid4().hex, source="manual")
        count += len(items)

    def expense(amount, category, desc, day, wallet=cash) -> TransactionIn:
        return TransactionIn(
            type="expense",
            amount=Decimal(amount),
            wallet_id=wallet,
            category_id=cat[category],
            description=desc,
            occurred_on=day,
        )

    def income(amount, category, desc, day, wallet) -> TransactionIn:
        return TransactionIn(
            type="income",
            amount=Decimal(amount),
            wallet_id=wallet,
            category_id=cat[category],
            description=desc,
            occurred_on=day,
        )

    start = _month_start(today, 2)
    day = start
    while day <= today:
        items: list[TransactionIn] = []
        if day.day == 1:
            items.append(income("8000", "Allowance", "Ammu's hatkhoroch", day, bkash))
            items.append(
                TransactionIn(
                    type="transfer",
                    amount=Decimal("3000"),
                    wallet_id=bkash,
                    to_wallet_id=cash,
                    description="Cash out",
                    occurred_on=day,
                )
            )
        if day.day == 10:
            items.append(income("6000", "Tuition", "Tuition fee — Class 8 student", day, bkash))
        if day.day == 18 and day.month % 2 == 0:
            items.append(income("12000", "Freelance", "Logo design project", day, bank))
        # Daily life
        items.append(expense(rng.choice(["20", "25", "30"]), "Food & Drinks", "Cha", day))
        if day.weekday() not in (4,):  # no class on Friday
            items.append(expense(str(rng.randrange(40, 130, 10)), "Transport", "Rickshaw", day))
            if rng.random() < 0.7:
                items.append(
                    expense(str(rng.randrange(120, 260, 10)), "Food & Drinks", "Lunch", day)
                )
        if day.weekday() == 5:  # Saturday bazar
            items.append(
                expense(str(rng.randrange(900, 2400, 50)), "Groceries", "Weekly bazar", day)
            )
        if day.day == 3:
            items.append(
                expense(
                    rng.choice(["199", "299"]), "Mobile & Internet", "Mobile recharge", day, bkash
                )
            )
        if rng.random() < 0.08:
            items.append(
                expense(str(rng.randrange(300, 1500, 50)), "Entertainment", "Movie & snacks", day)
            )
        if rng.random() < 0.05:
            items.append(
                expense(str(rng.randrange(500, 3500, 100)), "Shopping", "Clothes", day, bkash)
            )
        if rng.random() < 0.04:
            items.append(expense(str(rng.randrange(200, 900, 50)), "Healthcare", "Medicine", day))
        if day.day == 15 and rng.random() < 0.6:
            items.append(expense("650", "Education", "Books & photocopy", day))
        add(items)
        day += timedelta(days=1)

    # Monthly bills: paid in past months, unpaid this month if not yet due.
    rent = planning.create_bill(
        db, user_id, name="Mess rent", amount=Decimal("6500"), category_id=cat["Rent"],
        wallet_id=bkash, due_day=5,
    )  # fmt: skip
    wifi = planning.create_bill(
        db, user_id, name="Wi-Fi", amount=Decimal("700"), category_id=cat["Bills & Utilities"],
        wallet_id=bkash, due_day=12,
    )  # fmt: skip
    for back in (2, 1, 0):
        m = _month_start(today, back)
        for bill, due in ((rent, 5), (wifi, 12)):
            paid_on = m.replace(day=due)
            if paid_on <= today:
                planning.pay_bill(
                    db, user_id, bill.id, wallet_id=bkash, amount=None,
                    occurred_on=paid_on, idempotency_key=uuid.uuid4().hex,
                )  # fmt: skip

    # This month's budget from the deterministic engine.
    month = today.replace(day=1)
    draft = planning.draft_budget(
        db,
        user_id,
        planning.DraftInput(
            month=month,
            planned_income=Decimal("26000"),
            savings_target=Decimal("3000"),
            stated=[(cat["Food & Drinks"], Decimal("4500"), False)],
        ),
    )
    planning.save_budget(
        db,
        user_id,
        month,
        planned_income=Decimal(draft["planned_income"]),
        savings_target=Decimal(draft["savings_target"]),
        items=[(i["category"]["id"], i["amount"]) for i in draft["items"]],
        explanation="\n".join(draft["explanation"]),
    )
    planning.create_expected(
        db, user_id, source="Freelance — website project", amount=Decimal("15000"),
        expected_on=month.replace(day=25),
    )  # fmt: skip
    return {"transactions": count, "from": start, "to": today}
