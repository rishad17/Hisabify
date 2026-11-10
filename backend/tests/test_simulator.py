"""Purchase simulator verdicts — pure logic, no DB."""

from decimal import Decimal as D

import pytest

from app.services.simulator import CategoryBudget, Snapshot, evaluate


def snap(available="5000", savings="3000", flexible="4000", expected="0", confidence="good"):
    return Snapshot(
        available=D(available),
        savings_to_reserve=D(savings),
        flexible_budget_left=D(flexible) if flexible is not None else None,
        expected_income=D(expected),
        has_budget=flexible is not None,
        confidence=confidence,
        days_left=19,
    )


def test_affordable():
    s = evaluate(snap(), D("2500"), None)
    assert s.verdict == "affordable"
    assert s.available_after == D("2500")
    assert s.savings_shortfall == 0 and s.alternatives == []


def test_never_affordable_without_enough_information():
    s = evaluate(snap(flexible=None, confidence="limited"), D("100"), None)
    assert s.verdict == "likely_affordable"
    assert any("estimate" in r for r in s.reasons)


def test_over_category_budget_even_though_money_exists():
    cat = CategoryBudget("Shopping", D("1000"), is_essential=False)
    s = evaluate(snap(), D("2500"), cat)
    assert s.verdict == "over_budget"
    assert s.category_remaining_after == D("-1500")
    assert any("Shopping" in r and "1,500" in r for r in s.reasons)


def test_over_flexible_budget_without_category():
    s = evaluate(snap(flexible="1000"), D("2500"), None)
    assert s.verdict == "over_budget"


def test_cuts_into_savings():
    s = evaluate(snap(available="1000"), D("3000"), None)
    assert s.verdict == "cuts_into_savings"
    assert (s.savings_shortfall, s.savings_target_left) == (D("2000"), D("1000"))
    assert s.commitments_shortfall == 0
    assert any("Spend up to ৳1,000" in a for a in s.alternatives)


def test_not_affordable_when_bills_at_risk():
    s = evaluate(snap(available="1000", savings="500"), D("3000"), None)
    assert s.verdict == "not_affordable"
    assert (s.savings_shortfall, s.commitments_shortfall) == (D("500"), D("1500"))


def test_expected_income_alternative():
    s = evaluate(snap(available="1000", expected="4000"), D("3000"), None)
    assert s.affordable_after_expected_income is True
    assert s.alternatives[0].startswith("Wait until your expected income")


def test_already_overcommitted():
    s = evaluate(snap(available="-500", savings="0"), D("100"), None)
    assert s.verdict == "not_affordable"
    assert s.max_without_touching_savings == 0


def test_rejects_non_positive():
    with pytest.raises(ValueError):
        evaluate(snap(), D("0"), None)
