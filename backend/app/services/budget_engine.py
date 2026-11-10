"""Deterministic monthly budget builder. No AI, no database — just arithmetic.

Order of allocation (the "pay yourself first" approach):
  1. Savings target is set aside first.
  2. Fixed costs: amounts the user stated as fixed (rent, fees) and recurring bills.
  3. The user's own estimates ("food around 4,000").
  4. Whatever is left is spread across the remaining categories, in proportion to the
     user's own past spending (last 3 months) — or typical proportions if there's no
     history yet.

Guarantees (unit-tested):
  * every amount is a Decimal with 2 places; suggestions are rounded to ৳10
  * sum(items) + savings == planned income EXACTLY when there is money left over
    (the rounding remainder goes to Miscellaneous)
  * if commitments exceed income, NOTHING is invented: we return the shortfall instead
"""

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Any, Literal

ZERO = Decimal("0.00")
ROUND_TO = Decimal("10")
MISC = "Miscellaneous"

# Typical shares for someone with no history yet (students / young professionals in BD).
# Rent and Bills & Utilities are only budgeted when the user states them or has bills.
DEFAULT_WEIGHTS: dict[str, int] = {
    "Food & Drinks": 25,
    "Groceries": 18,
    "Transport": 14,
    "Mobile & Internet": 5,
    "Education": 6,
    "Healthcare": 5,
    "Shopping": 9,
    "Entertainment": 7,
    "Family & Gifts": 5,
    MISC: 6,
}
ONLY_WHEN_STATED = {"Rent", "Bills & Utilities"}

Source = Literal["fixed", "bill", "estimate", "suggested"]


@dataclass(frozen=True)
class EngineCategory:
    id: Any
    name: str
    is_essential: bool = False


@dataclass(frozen=True)
class Stated:
    """An amount the user gave for a category; `fixed` = must pay (rent), else estimate."""

    category_id: Any
    amount: Decimal
    fixed: bool


@dataclass(frozen=True)
class Bill:
    category_id: Any
    amount: Decimal
    name: str


@dataclass
class PlanItem:
    category_id: Any
    amount: Decimal
    source: Source


@dataclass
class BudgetPlan:
    planned_income: Decimal
    savings_target: Decimal
    items: list[PlanItem]
    shortfall: Decimal  # > 0 when commitments + savings exceed income
    basis: Literal["history", "typical", "none"]
    explanation: list[str] = field(default_factory=list)

    @property
    def allocated(self) -> Decimal:
        return sum((i.amount for i in self.items), ZERO)


def taka(amount: Decimal) -> str:
    """৳1,25,000 style (lakh grouping), dropping .00."""
    q = amount.quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    whole, _, frac = f"{abs(q):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}৳{whole}" + ("" if frac == "00" else f".{frac}")


def _round_down(amount: Decimal) -> Decimal:
    return (amount / ROUND_TO).to_integral_value(rounding=ROUND_DOWN) * ROUND_TO


def plan_budget(
    *,
    planned_income: Decimal,
    savings_target: Decimal,
    categories: list[EngineCategory],
    stated: list[Stated] = (),  # type: ignore[assignment]
    bills: list[Bill] = (),  # type: ignore[assignment]
    history: dict[Any, Decimal] | None = None,
) -> BudgetPlan:
    if planned_income < 0 or savings_target < 0:
        raise ValueError("income and savings must not be negative")
    income = planned_income.quantize(ZERO)
    savings = savings_target.quantize(ZERO)
    by_id = {c.id: c for c in categories}

    # 1–3: what the user told us, plus recurring bills (a stated amount wins over bills).
    allocations: dict[Any, PlanItem] = {}
    for s in stated:
        if s.category_id in by_id and s.amount > 0:
            prev = allocations.get(s.category_id)
            amount = s.amount.quantize(ZERO) + (prev.amount if prev else ZERO)
            allocations[s.category_id] = PlanItem(
                s.category_id, amount, "fixed" if s.fixed else "estimate"
            )
    for b in bills:
        if b.category_id in by_id and b.category_id not in {s.category_id for s in stated}:
            prev = allocations.get(b.category_id)
            allocations[b.category_id] = PlanItem(
                b.category_id, b.amount.quantize(ZERO) + (prev.amount if prev else ZERO), "bill"
            )

    fixed_total = sum(
        (a.amount for a in allocations.values() if a.source in ("fixed", "bill")), ZERO
    )
    estimate_total = sum((a.amount for a in allocations.values() if a.source == "estimate"), ZERO)
    left = income - savings - fixed_total - estimate_total

    explanation = [
        f"Money for the month: {taka(income)}.",
        f"Savings set aside first: {taka(savings)}.",
    ]
    if fixed_total:
        explanation.append(f"Fixed costs and bills: {taka(fixed_total)}.")
    if estimate_total:
        explanation.append(f"Your own estimates: {taka(estimate_total)}.")

    if left < 0:
        explanation.append(
            f"These add up to {taka(-left)} MORE than your money. Lower the savings target "
            "or some estimates — nothing else was allocated."
        )
        return BudgetPlan(income, savings, list(allocations.values()), -left, "none", explanation)

    # 4: spread what's left across the other categories.
    candidates = [
        c for c in categories if c.id not in allocations and c.name not in ONLY_WHEN_STATED
    ]
    history = history or {}
    hist_weights = {
        c.id: history.get(c.id, ZERO) for c in candidates if history.get(c.id, ZERO) > 0
    }
    if hist_weights:
        weights: dict[Any, Decimal] = hist_weights
        basis: Literal["history", "typical", "none"] = "history"
    else:
        weights = {
            c.id: Decimal(DEFAULT_WEIGHTS[c.name]) for c in candidates if c.name in DEFAULT_WEIGHTS
        }
        basis = "typical" if weights else "none"

    suggested: dict[Any, Decimal] = {}
    total_weight = sum(weights.values(), ZERO)
    if left > 0 and total_weight > 0:
        for cid, w in weights.items():
            suggested[cid] = _round_down(left * w / total_weight)

    # Put the rounding remainder (or everything, if nothing could be suggested) somewhere
    # visible so the budget adds up exactly.
    remainder = left - sum(suggested.values(), ZERO)
    if remainder > 0:
        misc = next((c for c in categories if c.name == MISC), None)
        target = misc.id if misc else (max(suggested, key=suggested.get) if suggested else None)
        if target is not None and target in allocations:
            allocations[target].amount += remainder
        elif target is not None:
            suggested[target] = suggested.get(target, ZERO) + remainder

    for cid, amount in suggested.items():
        if amount > 0:
            allocations[cid] = PlanItem(cid, amount.quantize(ZERO), "suggested")

    if left > 0:
        how = (
            "in proportion to your spending over the last 3 months"
            if basis == "history"
            else "using typical proportions (they'll adapt once you have some history)"
        )
        explanation.append(f"The remaining {taka(left)} was spread across other categories {how}.")

    items = sorted(allocations.values(), key=lambda i: (-i.amount, by_id[i.category_id].name))
    return BudgetPlan(income, savings, items, ZERO, basis, explanation)
