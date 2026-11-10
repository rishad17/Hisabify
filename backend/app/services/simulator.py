"""What-if purchase simulator: "If I buy X for ৳N, am I still OK this month?"

Never writes anything. Starts from the same commitment-aware snapshot as safe-to-spend:

    available = spendable money − unpaid bills − savings still to set aside − essentials left

then subtracts the purchase and explains which commitment would absorb any shortfall —
first the savings target, then bills and essentials. A purchase is only called
"affordable" when the app has enough information; otherwise it says "likely".
"""

import uuid
from dataclasses import dataclass, field
from decimal import ROUND_UP, Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.services import planning
from app.services.budget_engine import taka
from app.services.ledger import today_for

ZERO = Decimal("0.00")

Verdict = Literal[
    "affordable",  # money and budget both fine, enough information
    "likely_affordable",  # looks fine, but the app lacks a budget or bills to be sure
    "over_budget",  # money is there, but it breaks the category/flexible budget
    "cuts_into_savings",  # bills/essentials covered only by using savings
    "not_affordable",  # even using savings, bills or essentials would be short
]


@dataclass
class Snapshot:
    """The subset of safe-to-spend the simulator needs (easy to build in tests)."""

    available: Decimal
    savings_to_reserve: Decimal
    flexible_budget_left: Decimal | None
    expected_income: Decimal
    has_budget: bool
    confidence: Literal["good", "limited"]
    days_left: int


@dataclass
class CategoryBudget:
    name: str
    remaining: Decimal  # may be negative if already over
    is_essential: bool


@dataclass
class Simulation:
    amount: Decimal
    verdict: Verdict
    available_before: Decimal
    available_after: Decimal
    savings_target_left: Decimal  # savings you could still set aside after buying
    savings_shortfall: Decimal  # how much of the savings target you'd lose
    commitments_shortfall: Decimal  # bills/essentials you couldn't cover even with savings
    category_name: str | None
    category_remaining_after: Decimal | None
    flexible_budget_after: Decimal | None
    affordable_after_expected_income: bool | None
    max_without_touching_savings: Decimal
    reasons: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


def evaluate(snap: Snapshot, amount: Decimal, category: CategoryBudget | None) -> Simulation:
    if amount <= 0:
        raise ValueError("amount must be positive")
    after = snap.available - amount
    shortfall = max(ZERO, -after)
    savings_hit = min(shortfall, snap.savings_to_reserve)
    commitments_short = shortfall - savings_hit

    cat_after = category.remaining - amount if category else None
    flex_after = (
        snap.flexible_budget_left - amount if snap.flexible_budget_left is not None else None
    )
    over_budget = (cat_after is not None and cat_after < 0) or (
        cat_after is None and flex_after is not None and flex_after < 0
    )

    if commitments_short > 0:
        verdict: Verdict = "not_affordable"
    elif savings_hit > 0:
        verdict = "cuts_into_savings"
    elif over_budget:
        verdict = "over_budget"
    elif snap.confidence == "good":
        verdict = "affordable"
    else:
        verdict = "likely_affordable"

    reasons: list[str] = []
    if verdict in ("affordable", "likely_affordable", "over_budget"):
        reasons.append(
            f"After buying, {taka(after)} stays free after bills, savings and essentials."
        )
    if savings_hit > 0:
        reasons.append(
            f"You'd have to use {taka(savings_hit)} of this month's "
            f"{taka(snap.savings_to_reserve)} savings target."
        )
    if commitments_short > 0:
        reasons.append(
            f"Even using all savings, you'd be {taka(commitments_short)} short for bills "
            "and essentials."
        )
    if category and cat_after is not None and cat_after < 0:
        reasons.append(f"It puts {category.name} {taka(-cat_after)} over its budget.")
    elif category is None and flex_after is not None and flex_after < 0:
        reasons.append(f"It's {taka(-flex_after)} more than your flexible budget has left.")
    if snap.confidence == "limited":
        reasons.append(
            "This is an estimate: without a budget and bills, the app can't reserve everything."
        )

    alternatives: list[str] = []
    max_free = max(ZERO, snap.available)
    if verdict in ("cuts_into_savings", "not_affordable", "over_budget"):
        if max_free > 0:
            alternatives.append(f"Spend up to {taka(max_free)} without touching savings or bills.")
        if snap.days_left > 0 and verdict != "over_budget":
            next_month_part = (amount / 2).quantize(Decimal("1"), rounding=ROUND_UP)
            if snap.available - next_month_part >= 0:
                alternatives.append(
                    f"Split it: pay about {taka(next_month_part)} now and the rest next month."
                )
        alternatives.append("Wait until next month, when your budget resets.")
    after_expected = None
    if snap.expected_income > 0 and after < 0:
        after_expected = after + snap.expected_income >= 0
        if after_expected:
            alternatives.insert(
                0,
                f"Wait until your expected income ({taka(snap.expected_income)}) arrives — "
                "then it fits.",
            )

    return Simulation(
        amount=amount,
        verdict=verdict,
        available_before=snap.available,
        available_after=after,
        savings_target_left=snap.savings_to_reserve - savings_hit,
        savings_shortfall=savings_hit,
        commitments_shortfall=commitments_short,
        category_name=category.name if category else None,
        category_remaining_after=cat_after,
        flexible_budget_after=flex_after,
        affordable_after_expected_income=after_expected,
        max_without_touching_savings=max_free,
        reasons=reasons,
        alternatives=alternatives,
    )


def simulate_purchase(
    db: Session, user_id: uuid.UUID, amount: Decimal, category_id: uuid.UUID | None
) -> Simulation:
    """Read-only: builds the snapshot from real data and evaluates the purchase."""
    s = planning.safe_to_spend(db, user_id)
    snap = Snapshot(
        available=s["available"],
        savings_to_reserve=s["savings_to_reserve"],
        flexible_budget_left=s["flexible_budget_left"],
        expected_income=s["expected_income"],
        has_budget=s["has_budget"],
        confidence=s["confidence"],
        days_left=s["days_left"],
    )
    category = None
    if category_id is not None:
        cat = planning._check_expense_category(db, user_id, category_id)
        status = planning.budget_status(db, user_id, planning._month_start(today_for(db, user_id)))
        item = (
            next((i for i in status["items"] if i["category"]["id"] == cat.id), None)
            if status
            else None
        )
        if item is not None:
            category = CategoryBudget(cat.name, item["remaining"], cat.is_essential)
    return evaluate(snap, amount, category)
