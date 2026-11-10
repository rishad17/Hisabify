"""Budgets, bills, expected income, safe-to-spend, AI budget (needs PostgreSQL)."""

import uuid
from datetime import datetime
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from app.ai.llm_client import LLMResult
from app.ai.rate_limit import RateLimiter
from tests.test_ledger import Api

pytestmark = pytest.mark.db


def this_month() -> str:
    return datetime.now(ZoneInfo("Asia/Dhaka")).date().strftime("%Y-%m")


def key() -> dict:
    return {"Idempotency-Key": uuid.uuid4().hex}


@pytest.fixture
def api(db_client, make_token) -> Api:
    return Api(db_client, make_token())


@pytest.fixture
def other(db_client, make_token) -> Api:
    return Api(db_client, make_token())


def save_budget(api: Api, items: dict[str, str], income="20000", savings="3000"):
    r = api.c.put(
        f"/api/v1/budgets/{this_month()}",
        headers=api.h,
        json={
            "planned_income": income,
            "savings_target": savings,
            "items": [{"category_id": api.cat[n], "amount": a} for n, a in items.items()],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["budget"]


def add_bill(api: Api, name="House rent", amount="5000", category="Rent", due_day=5) -> str:
    r = api.post(
        "/bills",
        {"name": name, "amount": amount, "category_id": api.cat[category], "due_day": due_day},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ------------------------------------------------------------------ budget draft


def test_draft_adds_up_and_includes_bills(api):
    add_bill(api, "Wifi", "1000", "Bills & Utilities")
    r = api.post(
        "/budgets/draft",
        {
            "month": this_month(),
            "planned_income": "20000",
            "savings_target": "3000",
            "stated": [{"category_id": api.cat["Rent"], "amount": "5000", "fixed": True}],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    total = sum(D(i["amount"]) for i in d["items"]) + D(d["savings_target"])
    assert total == D("20000")
    assert d["unallocated"] == "0.00" and d["shortfall"] == "0.00"
    sources = {i["category"]["name"]: i["source"] for i in d["items"]}
    assert sources["Rent"] == "fixed" and sources["Bills & Utilities"] == "bill"
    assert api.get(f"/budgets/{this_month()}").json() == {"budget": None}  # nothing saved


def test_draft_shortfall(api):
    d = api.post(
        "/budgets/draft",
        {
            "month": this_month(),
            "planned_income": "5000",
            "savings_target": "1000",
            "stated": [{"category_id": api.cat["Rent"], "amount": "6000", "fixed": True}],
        },
    ).json()
    assert d["shortfall"] == "2000.00"
    assert [i["category"]["name"] for i in d["items"]] == ["Rent"]


def test_draft_uses_spending_history(api):
    from datetime import timedelta

    dhaka_today = datetime.now(ZoneInfo("Asia/Dhaka")).date()
    last_month = (dhaka_today.replace(day=1) - timedelta(days=1)).isoformat()
    api.save(api.expense("3000", "Food & Drinks", occurred_on=last_month))
    api.save(api.expense("1000", "Transport", occurred_on=last_month))
    d = api.post(
        "/budgets/draft", {"month": this_month(), "planned_income": "8000", "savings_target": "0"}
    ).json()
    assert d["basis"] == "history"
    amounts = {i["category"]["name"]: i["amount"] for i in d["items"]}
    assert amounts == {"Food & Drinks": "6000.00", "Transport": "2000.00"}


# ------------------------------------------------------------------ saved budget


def test_save_and_track_budget_vs_actual(api):
    save_budget(api, {"Food & Drinks": "4000", "Transport": "2000"})
    api.save(api.expense("3200", "Food & Drinks"), api.expense("150", "Shopping"))
    b = api.get(f"/budgets/{this_month()}").json()["budget"]
    food = next(i for i in b["items"] if i["category"]["name"] == "Food & Drinks")
    assert (food["spent"], food["remaining"], food["percent_used"]) == ("3200.00", "800.00", 80)
    assert b["unbudgeted_spent"] == "150.00"
    assert (b["total_budget"], b["total_spent"]) == ("6000.00", "3350.00")


def test_save_replaces_and_delete(api):
    save_budget(api, {"Food & Drinks": "4000"})
    b = save_budget(api, {"Transport": "1000"}, income="9000")
    assert [i["category"]["name"] for i in b["items"]] == ["Transport"]
    assert b["planned_income"] == "9000.00"
    assert api.c.delete(f"/api/v1/budgets/{this_month()}", headers=api.h).status_code == 204
    assert api.get(f"/budgets/{this_month()}").json() == {"budget": None}


def test_budget_validation_and_isolation(api, other):
    url = f"/api/v1/budgets/{this_month()}"
    bad = {"planned_income": "100", "items": [{"category_id": api.cat["Salary"], "amount": "10"}]}
    assert (
        api.c.put(url, headers=api.h, json=bad).json()["error"]["code"] == "category_kind_mismatch"
    )
    dup = {
        "planned_income": "100",
        "items": [{"category_id": api.cat["Rent"], "amount": "10"}] * 2,
    }
    assert api.c.put(url, headers=api.h, json=dup).json()["error"]["code"] == "duplicate_category"
    foreign = {"planned_income": "100", "items": [{"category_id": api.cat["Rent"], "amount": "1"}]}
    assert other.c.put(url, headers=other.h, json=foreign).status_code == 404
    assert api.get("/budgets/2026-13").status_code == 422


# ------------------------------------------------------------------ bills


def test_bill_lifecycle(api):
    bill_id = add_bill(api)
    api.save(api.income("10000"))
    bills = api.get("/bills").json()
    assert bills[0]["paid"] is False and bills[0]["due_date"].endswith("-05")

    k = key()
    r = api.post(f"/bills/{bill_id}/pay", {}, headers=k)
    assert r.status_code == 201, r.text
    tx = r.json()
    assert (tx["amount"], tx["description"], tx["category"]["name"]) == (
        "5000.00",
        "House rent",
        "Rent",
    )
    assert api.balance("Cash") == D("5000.00")
    assert api.get("/bills").json()[0]["paid"] is True

    # Retrying the same request returns the same payment; a new one is refused.
    assert api.post(f"/bills/{bill_id}/pay", {}, headers=k).json()["id"] == tx["id"]
    again = api.post(f"/bills/{bill_id}/pay", {}, headers=key())
    assert again.json()["error"]["code"] == "bill_already_paid"
    assert api.balance("Cash") == D("5000.00")

    # Voiding the payment makes the bill unpaid again.
    api.post(f"/transactions/{tx['id']}/void")
    assert api.get("/bills").json()[0]["paid"] is False

    # Deleting a bill keeps transaction history.
    assert api.c.delete(f"/api/v1/bills/{bill_id}", headers=api.h).status_code == 204
    assert api.get("/bills").json() == []


def test_bill_validation_and_isolation(api, other):
    r = api.post(
        "/bills", {"name": "x", "amount": "10", "category_id": api.cat["Salary"], "due_day": 1}
    )
    assert r.json()["error"]["code"] == "category_kind_mismatch"
    r = api.post(
        "/bills", {"name": "x", "amount": "10", "category_id": api.cat["Rent"], "due_day": 32}
    )
    assert r.status_code == 422
    bill_id = add_bill(api)
    assert other.post(f"/bills/{bill_id}/pay", {}, headers=key()).status_code == 404
    assert other.get("/bills").json() == []


# ------------------------------------------------------------------ expected income


def test_expected_income_receive_and_cancel(api):
    today = datetime.now(ZoneInfo("Asia/Dhaka")).date().isoformat()
    e = api.post(
        "/expected-incomes", {"source": "Tuition fee", "amount": "4000", "expected_on": today}
    ).json()
    assert e["status"] == "expected"
    assert api.balance("Cash") == D("0.00")  # expected ≠ received

    k = key()
    body = {"wallet_id": api.cash, "category_id": api.cat["Tuition"]}
    r = api.post(f"/expected-incomes/{e['id']}/receive", body, headers=k)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"
    assert api.balance("Cash") == D("4000.00")
    api.post(f"/expected-incomes/{e['id']}/receive", body, headers=k)  # retry
    assert api.balance("Cash") == D("4000.00")
    assert api.get("/expected-incomes").json() == []  # closed items hidden by default

    e2 = api.post(
        "/expected-incomes", {"source": "Freelance", "amount": "100", "expected_on": today}
    ).json()
    assert api.post(f"/expected-incomes/{e2['id']}/cancel").json()["status"] == "cancelled"
    r = api.patch(f"/expected-incomes/{e2['id']}", {"amount": "5"})
    assert r.json()["error"]["code"] == "expected_income_closed"


# ------------------------------------------------------------------ safe to spend


def test_safe_to_spend_reserves_commitments(api):
    api.save(api.income("20000", "Salary"))
    add_bill(api, "House rent", "5000", "Rent")
    save_budget(api, {"Rent": "5000", "Groceries": "2000", "Food & Drinks": "4000"})
    api.save(api.expense("500", "Groceries"), api.expense("1000", "Food & Drinks"))
    today = datetime.now(ZoneInfo("Asia/Dhaka")).date().isoformat()
    api.post("/expected-incomes", {"source": "Tuition", "amount": "2000", "expected_on": today})

    s = api.get("/planning/safe-to-spend").json()
    assert s["spendable_balance"] == "18500.00"
    assert s["unpaid_bills"] == "5000.00"
    assert s["savings_to_reserve"] == "3000.00"
    assert s["essentials_to_reserve"] == "1500.00"  # groceries left; rent covered by the bill
    assert s["available"] == "9000.00"
    assert s["flexible_budget_left"] == "3000.00"  # food budget left
    assert s["recommended"] == "3000.00"  # limited by the budget, not the money
    assert D(s["per_day"]) == (D("3000") / s["days_left"]).to_integral_value(rounding="ROUND_DOWN")
    assert s["expected_income"] == "2000.00"
    assert s["available_if_expected_arrives"] == "11000.00"
    assert s["confidence"] == "good"

    # Paying the bill or saving money moves money, but the available amount stays the same.
    bill_id = api.get("/bills").json()[0]["id"]
    api.post(f"/bills/{bill_id}/pay", {}, headers=key())
    savings = api.new_wallet("Savings", "savings")
    api.save({"type": "transfer", "amount": "1000", "wallet_id": api.cash, "to_wallet_id": savings})
    s2 = api.get("/planning/safe-to-spend").json()
    assert (s2["unpaid_bills"], s2["savings_to_reserve"]) == ("0.00", "2000.00")
    assert s2["spendable_balance"] == "12500.00"
    assert s2["available"] == "9000.00"


def test_safe_to_spend_without_budget_is_honest(api):
    api.save(api.income("1000"))
    s = api.get("/planning/safe-to-spend").json()
    assert s["has_budget"] is False and s["confidence"] == "limited"
    assert s["recommended"] == "1000.00"
    assert any("No budget" in n for n in s["notes"])


def test_safe_to_spend_overcommitted(api):
    api.save(api.income("1000"))
    add_bill(api, "Rent", "5000", "Rent")
    s = api.get("/planning/safe-to-spend").json()
    assert s["available"] == "-4000.00"
    assert s["recommended"] == "0.00" and s["per_day"] == "0.00"
    assert "exceed" in s["notes"][0]


# ------------------------------------------------------------------ AI budget


class FakeLLM:
    def __init__(self, data):
        self.data = data

    def generate_json(self, **kwargs):
        return LLMResult(self.data, "fake", 1, 1, 1)


def ai_budget(db_client, api, data, text="I have 20,000. Rent 5000, food 4000, save 3000"):
    db_client.app.state.llm = FakeLLM(data)
    db_client.app.state.ai_rate_limiter = RateLimiter(100)
    return api.post("/ai/budget", {"text": text, "month": this_month()})


def test_ai_budget_extracts_then_engine_calculates(db_client, api):
    r = ai_budget(
        db_client,
        api,
        {
            "planned_income": "20,000",
            "savings_target": "3000",
            "items": [
                {"category": "Rent", "amount": "5000", "fixed": True},
                {"category": "Food & Drinks", "amount": "4000", "fixed": False},
                {"category": "Not a category", "amount": "99", "fixed": False},
            ],
            "clarification": None,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "budget_draft"
    assert body["understood"]["planned_income"] == "20000.00"
    assert len(body["understood"]["items"]) == 2  # unknown category dropped
    d = body["draft"]
    assert sum(D(i["amount"]) for i in d["items"]) + D(d["savings_target"]) == D("20000")


def test_ai_budget_asks_when_income_missing(db_client, api):
    r = ai_budget(
        db_client,
        api,
        {"planned_income": None, "savings_target": None, "items": [], "clarification": None},
        text="make me a budget",
    )
    body = r.json()
    assert body["kind"] == "clarification" and body["draft"] is None
    assert "money" in body["message"]
