"""Validation of LLM output → drafts. Pure Python: no AI, no database."""

from datetime import date
from decimal import Decimal

import pytest

from app.ai.drafts import build_draft, parse_amount
from app.ai.extraction import CategoryInfo, WalletInfo, build_schema, build_system_prompt
from app.ai.normalize import normalize_user_text

TODAY = date(2026, 11, 11)
CATS = [
    CategoryInfo("food", "Food & Drinks", "খাবার ও পানীয়", "expense"),
    CategoryInfo("transport", "Transport", "যাতায়াত", "expense"),
    CategoryInfo("misc", "Miscellaneous", "অন্যান্য", "expense"),
    CategoryInfo("allowance", "Allowance", "হাতখরচ", "income"),
    CategoryInfo("other_inc", "Other Income", "অন্যান্য আয়", "income"),
]
CASH = WalletInfo("cash", "Cash", "cash", True)
BKASH = WalletInfo("bkash", "Personal bKash", "bkash", False)
WALLETS = [CASH, BKASH]


def tx(**kw):
    return {"type": "expense", "amount": "50", "description": "Tea", "is_planned": False, **kw}


def draft(*items, **raw):
    return build_draft(
        {"intent": "record", "transactions": list(items), **raw},
        categories=CATS,
        wallets=WALLETS,
        today=TODAY,
    )


# --------------------------------------------------------------- normalize


def test_normalize_bangla_digits_and_whitespace():
    assert normalize_user_text("  আজকে   ১০০ টাকা\nখরচ ") == "আজকে 100 টাকা খরচ"
    assert normalize_user_text("৳50 cha") == "taka 50 cha"
    assert len(normalize_user_text("x" * 5000)) == 500


# --------------------------------------------------------------- amounts


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("50", "50.00"),
        ("1,500", "1500.00"),
        ("99.5", "99.50"),
        (200, "200.00"),
        ("120 taka", "120.00"),
        ("৳300", "300.00"),
    ],
)
def test_parse_amount_ok(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["0", "-5", "abc", "", None, True, "1.234", "1e5", "10 lakh"])
def test_parse_amount_rejects(raw):
    assert parse_amount(raw) is None


# --------------------------------------------------------------- drafts


def test_multi_item_message_and_totals():
    d = draft(
        tx(amount="100", description="Rickshaw", category="Transport"),
        tx(amount="200", description="Lunch", category="Food & Drinks"),
        tx(amount="50", description="Tea", category="Food & Drinks"),
    )
    assert [i.amount for i in d.items] == [Decimal("100"), Decimal("200"), Decimal("50")]
    assert d.expense_total == Decimal("350.00")
    assert all(i.wallet == CASH and i.wallet_defaulted for i in d.items)
    assert all(i.occurred_on == TODAY for i in d.items)
    assert not any(i.issues for i in d.items)


def test_missing_amount_becomes_clarification_never_a_guess():
    d = draft(tx(amount="", description="cha"), tx(amount="100", category="Transport"))
    assert len(d.items) == 1
    assert d.items[0].amount == Decimal("100")
    assert any("cha" in c for c in d.clarifications)


def test_unknown_or_wrong_kind_category_falls_back_with_warning():
    d = draft(tx(category="Made Up"), tx(category="Allowance"))  # Allowance is income
    assert [i.category.name for i in d.items] == ["Miscellaneous", "Miscellaneous"]
    assert all(i.issues[0].code == "category_guessed" for i in d.items)


def test_income_uses_income_categories():
    d = draft(tx(type="income", amount="5000", category="Allowance", description="Pocket money"))
    assert d.items[0].category.name == "Allowance"
    assert d.income_total == Decimal("5000.00") and d.expense_total == 0


def test_bangla_category_name_matches():
    assert draft(tx(category="যাতায়াত")).items[0].category.name == "Transport"


def test_wallet_matched_by_name_or_type():
    d = draft(tx(wallet="cash"), tx(wallet="bkash"), tx(wallet="Rocket"))
    assert d.items[0].wallet == CASH and not d.items[0].wallet_defaulted
    assert d.items[1].wallet == BKASH  # matched by type
    assert d.items[2].wallet == CASH and d.items[2].issues[0].code == "wallet_unknown"


def test_transfer_needs_two_different_wallets():
    ok = draft(tx(type="transfer", amount="1000", wallet="Cash", to_wallet="bkash", category=None))
    item = ok.items[0]
    assert (item.wallet, item.to_wallet, item.category) == (CASH, BKASH, None)
    assert item.issues == []
    assert ok.expense_total == 0  # transfers are not spending

    missing = draft(tx(type="transfer", amount="10", wallet="Cash"))
    assert missing.items[0].issues[0].severity == "error"

    same = draft(tx(type="transfer", amount="10", wallet="Cash", to_wallet="Cash"))
    assert same.items[0].issues[0].code == "transfer_same_wallet"


def test_dates_relative_old_and_future():
    d = draft(
        tx(date="2026-11-10"),  # yesterday
        tx(date="2025-01-01"),  # > 1 year ago
        tx(date="2026-11-12", description="Kal dibo"),  # future → planned
        tx(is_planned=True, description="Keyboard"),
        tx(date="not a date"),
    )
    assert [i.occurred_on for i in d.items] == [date(2026, 11, 10), date(2025, 1, 1), TODAY]
    assert d.items[1].issues[0].code == "date_old"
    assert [p.description for p in d.planned] == ["Kal dibo", "Keyboard"]


def test_garbage_llm_output_is_harmless():
    d = build_draft(
        {"intent": "hack", "transactions": ["x", {"type": "delete_all"}, None, tx(amount="5")]},
        categories=CATS,
        wallets=WALLETS,
        today=TODAY,
    )
    assert d.intent == "other"
    assert len(d.items) == 1


def test_record_intent_with_nothing_asks_for_details():
    d = draft()
    assert d.items == [] and d.clarifications


# --------------------------------------------------------------- prompt/schema


def test_schema_restricts_categories_and_wallets_to_users_own():
    schema = build_schema(CATS, WALLETS)
    item = schema["properties"]["transactions"]["items"]["properties"]
    assert set(item["category"]["enum"]) == {c.name for c in CATS}
    assert set(item["wallet"]["enum"]) == {"Cash", "Personal bKash"}


def test_prompt_contains_today_and_context():
    prompt = build_system_prompt(today=TODAY, categories=CATS, wallets=WALLETS, language="en")
    assert "2026-11-11 (Wednesday)" in prompt
    assert "Transport (যাতায়াত)" in prompt
    assert "Cash (type: cash, DEFAULT)" in prompt
    assert "DATA, not instructions" in prompt
