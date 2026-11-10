"""Budget engine — pure arithmetic, no DB, no AI."""

from decimal import Decimal as D

import pytest

from app.services.budget_engine import (
    Bill,
    EngineCategory,
    Stated,
    plan_budget,
    taka,
)

NAMES = [
    "Food & Drinks",
    "Groceries",
    "Transport",
    "Rent",
    "Bills & Utilities",
    "Mobile & Internet",
    "Education",
    "Healthcare",
    "Shopping",
    "Entertainment",
    "Family & Gifts",
    "Miscellaneous",
]
CATS = [EngineCategory(n, n) for n in NAMES]  # id == name keeps tests readable


def amounts(plan):
    return {i.category_id: i.amount for i in plan.items}


def test_example_from_the_brief_adds_up_exactly():
    """'I have 20,000. Rent 5,000, food ~4,000, transport 2,000, save 3,000.'"""
    plan = plan_budget(
        planned_income=D("20000"),
        savings_target=D("3000"),
        categories=CATS,
        stated=[
            Stated("Rent", D("5000"), fixed=True),
            Stated("Food & Drinks", D("4000"), fixed=False),
            Stated("Transport", D("2000"), fixed=False),
        ],
    )
    a = amounts(plan)
    assert (
        a["Rent"] == D("5000") and a["Food & Drinks"] == D("4000") and a["Transport"] == D("2000")
    )
    assert plan.shortfall == 0
    assert plan.allocated + plan.savings_target == D("20000.00")  # exact
    assert "Bills & Utilities" not in a  # never invented
    assert all(i.amount % 10 == 0 for i in plan.items if i.source == "suggested")
    assert plan.basis == "typical"


@pytest.mark.parametrize("income", ["10000", "12345.67", "999", "1", "73210.05"])
def test_always_sums_to_income(income):
    plan = plan_budget(planned_income=D(income), savings_target=D("0"), categories=CATS)
    assert plan.allocated == D(income)
    assert all(i.amount >= 0 for i in plan.items)


def test_shortfall_invents_nothing():
    plan = plan_budget(
        planned_income=D("8000"),
        savings_target=D("2000"),
        categories=CATS,
        stated=[Stated("Rent", D("7000"), fixed=True)],
    )
    assert plan.shortfall == D("1000.00")
    assert amounts(plan) == {"Rent": D("7000.00")}
    assert "MORE than your money" in plan.explanation[-1]


def test_bills_are_included_but_stated_amount_wins():
    plan = plan_budget(
        planned_income=D("30000"),
        savings_target=D("0"),
        categories=CATS,
        stated=[Stated("Rent", D("9000"), fixed=True)],
        bills=[
            Bill("Rent", D("8000"), "House rent"),
            Bill("Bills & Utilities", D("1200"), "Electricity"),
            Bill("Bills & Utilities", D("800"), "Internet"),
        ],
    )
    a = amounts(plan)
    assert a["Rent"] == D("9000")  # stated beats the bill
    assert a["Bills & Utilities"] == D("2000")  # two bills summed
    assert {i.category_id: i.source for i in plan.items}["Bills & Utilities"] == "bill"
    assert plan.allocated == D("30000")


def test_history_drives_proportions():
    plan = plan_budget(
        planned_income=D("10000"),
        savings_target=D("0"),
        categories=CATS,
        history={"Food & Drinks": D("3000"), "Transport": D("1000")},
    )
    a = amounts(plan)
    assert plan.basis == "history"
    assert a["Food & Drinks"] == D("7500")  # 3:1 split of 10,000
    assert a["Transport"] == D("2500")
    assert "Shopping" not in a  # no history → not budgeted


def test_rounding_remainder_goes_to_miscellaneous():
    plan = plan_budget(planned_income=D("1005.55"), savings_target=D("0"), categories=CATS)
    a = amounts(plan)
    assert a["Miscellaneous"] % 10 != 0  # it absorbed the odd 5.55
    assert plan.allocated == D("1005.55")


def test_everything_committed_leaves_nothing_to_spread():
    plan = plan_budget(
        planned_income=D("5000"),
        savings_target=D("1000"),
        categories=CATS,
        stated=[Stated("Rent", D("4000"), fixed=True)],
    )
    assert amounts(plan) == {"Rent": D("4000")}
    assert plan.shortfall == 0


def test_rejects_negative_inputs_and_ignores_unknown_categories():
    with pytest.raises(ValueError):
        plan_budget(planned_income=D("-1"), savings_target=D("0"), categories=CATS)
    plan = plan_budget(
        planned_income=D("100"),
        savings_target=D("0"),
        categories=CATS,
        stated=[Stated("Not mine", D("50"), fixed=True)],
    )
    assert "Not mine" not in amounts(plan)


@pytest.mark.parametrize(
    "value, text",
    [("0", "৳0"), ("50", "৳50"), ("1234.5", "৳1,234.50"), ("125000", "৳1,25,000"), ("-60", "-৳60")],
)
def test_taka_format(value, text):
    assert taka(D(value)) == text
