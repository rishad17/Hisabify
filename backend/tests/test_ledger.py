"""Ledger tests: balances, transfers, edits, voids, idempotency, isolation (needs PostgreSQL).

Everything goes through the HTTP API, exactly like the frontend uses it.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import auth_header

pytestmark = pytest.mark.db


class Api:
    """Tiny test helper representing one signed-in user."""

    def __init__(self, client, token: str) -> None:
        self.c = client
        self.h = auth_header(token)
        assert self.c.get("/api/v1/me", headers=self.h).status_code == 200
        cats = self.c.get("/api/v1/categories", headers=self.h).json()
        self.cat = {c["name"]: c["id"] for c in cats}
        self.cash = self.wallets()["Cash"]["id"]

    def get(self, path, **kw):
        return self.c.get(f"/api/v1{path}", headers=self.h, **kw)

    def post(self, path, json=None, headers=None):
        return self.c.post(f"/api/v1{path}", headers={**self.h, **(headers or {})}, json=json)

    def patch(self, path, json):
        return self.c.patch(f"/api/v1{path}", headers=self.h, json=json)

    def wallets(self) -> dict[str, dict]:
        return {w["name"]: w for w in self.get("/wallets").json()}

    def balance(self, name: str) -> Decimal:
        return Decimal(self.wallets()[name]["balance"])

    def new_wallet(self, name: str, type_: str = "bkash", opening: str = "0") -> str:
        r = self.post("/wallets", {"name": name, "type": type_, "opening_balance": opening})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def save(self, *items: dict, key: str | None = None, expect: int = 201):
        r = self.post(
            "/transactions/batch",
            {"items": list(items)},
            headers={"Idempotency-Key": key or uuid.uuid4().hex},
        )
        assert r.status_code == expect, r.text
        return r.json()

    def expense(self, amount: str, category="Food & Drinks", wallet=None, **extra) -> dict:
        return {
            "type": "expense",
            "amount": amount,
            "wallet_id": wallet or self.cash,
            "category_id": self.cat[category],
            **extra,
        }

    def income(self, amount: str, category="Allowance", wallet=None, **extra) -> dict:
        return {
            "type": "income",
            "amount": amount,
            "wallet_id": wallet or self.cash,
            "category_id": self.cat[category],
            **extra,
        }


@pytest.fixture
def api(db_client, make_token) -> Api:
    return Api(db_client, make_token())


@pytest.fixture
def other(db_client, make_token) -> Api:
    return Api(db_client, make_token())


def dhaka_today() -> date:
    from datetime import datetime

    return datetime.now(ZoneInfo("Asia/Dhaka")).date()


# ------------------------------------------------------------------ balances


def test_new_wallet_starts_at_opening_balance(api):
    api.new_wallet("bKash", opening="1500.50")
    assert api.balance("bKash") == Decimal("1500.50")
    assert api.balance("Cash") == Decimal("0.00")


def test_income_and_expense_update_balance(api):
    api.save(api.income("5000"), api.expense("50"), api.expense("120.75", "Transport"))
    assert api.balance("Cash") == Decimal("4829.25")


def test_multi_item_batch_returns_items_in_order(api):
    body = api.save(api.expense("100", "Transport"), api.expense("200"), api.expense("50"))
    assert [i["amount"] for i in body["items"]] == ["100.00", "200.00", "50.00"]
    assert body["replayed"] is False
    assert body["items"][0]["category"]["name_bn"] == "যাতায়াত"


def test_transfer_moves_money_and_is_not_an_expense(api):
    bkash = api.new_wallet("bKash")
    api.save(api.income("3000"))
    api.save({"type": "transfer", "amount": "1000", "wallet_id": api.cash, "to_wallet_id": bkash})

    assert api.balance("Cash") == Decimal("2000.00")
    assert api.balance("bKash") == Decimal("1000.00")

    overview = api.get("/analytics/overview").json()
    assert overview["expense"] == "0.00"
    assert overview["income"] == "3000.00"
    assert overview["total_balance"] == "3000.00"  # money moved, not spent


def test_void_removes_effect_everywhere(api):
    tx = api.save(api.expense("300"))["items"][0]
    assert api.balance("Cash") == Decimal("-300.00")

    r = api.post(f"/transactions/{tx['id']}/void")
    assert r.status_code == 200 and r.json()["voided"] is True
    assert api.balance("Cash") == Decimal("0.00")
    assert api.get("/transactions").json()["total"] == 0
    assert api.get("/analytics/overview").json()["expense"] == "0.00"


def test_edit_recomputes_balances(api):
    bkash = api.new_wallet("bKash")
    tx = api.save(api.expense("200"))["items"][0]

    r = api.patch(f"/transactions/{tx['id']}", {"amount": "250", "wallet_id": bkash})
    assert r.status_code == 200, r.text
    assert r.json()["wallet_name"] == "bKash"
    assert api.balance("Cash") == Decimal("0.00")
    assert api.balance("bKash") == Decimal("-250.00")


def test_edit_expense_to_transfer_clears_category(api):
    bkash = api.new_wallet("bKash")
    tx = api.save(api.expense("500"))["items"][0]
    r = api.patch(f"/transactions/{tx['id']}", {"type": "transfer", "to_wallet_id": bkash})
    assert r.status_code == 200, r.text
    assert r.json()["category"] is None
    assert api.balance("bKash") == Decimal("500.00")


def test_set_balance_creates_adjustment(api):
    api.save(api.income("1000"))
    r = api.post(f"/wallets/{api.cash}/set-balance", {"balance": "940"})
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "adjustment"
    assert r.json()["amount"] == "-60.00"
    assert api.balance("Cash") == Decimal("940.00")
    # Adjustments are corrections, not spending.
    assert api.get("/analytics/overview").json()["expense"] == "0.00"

    # Already correct → nothing created.
    assert api.post(f"/wallets/{api.cash}/set-balance", {"balance": "940.00"}).json() is None


def test_balances_always_equal_sum_of_history(api):
    """Property-style check: after a mixed sequence, total balance == income − expense
    + opening balances + adjustments (transfers cancel out)."""
    bkash = api.new_wallet("bKash", opening="500")
    nagad = api.new_wallet("Nagad", "nagad", opening="250.25")
    ops = [
        api.income("10000", "Tuition"),
        api.expense("1234.56", "Groceries"),
        {"type": "transfer", "amount": "2000", "wallet_id": api.cash, "to_wallet_id": bkash},
        {"type": "transfer", "amount": "700", "wallet_id": bkash, "to_wallet_id": nagad},
        api.expense("99.99", "Mobile & Internet", wallet=nagad),
        api.income("300", "Refund", wallet=bkash),
    ]
    api.save(*ops)
    total = sum(Decimal(w["balance"]) for w in api.wallets().values())
    assert total == Decimal("500") + Decimal("250.25") + Decimal("10000") + Decimal(
        "300"
    ) - Decimal("1234.56") - Decimal("99.99")
    assert api.balance("Cash") == Decimal("6765.44")
    assert api.balance("bKash") == Decimal("2100.00")
    assert api.balance("Nagad") == Decimal("850.26")


# ------------------------------------------------------------------ idempotency


def test_same_idempotency_key_never_duplicates(api):
    first = api.save(api.expense("50"), api.expense("20"), key="double-click-key-1")
    second = api.save(api.expense("50"), api.expense("20"), key="double-click-key-1")
    assert second["replayed"] is True
    assert [i["id"] for i in second["items"]] == [i["id"] for i in first["items"]]
    assert api.get("/transactions").json()["total"] == 2
    assert api.balance("Cash") == Decimal("-70.00")


def test_idempotency_keys_are_per_user(api, other):
    api.save(api.expense("50"), key="shared-key-123")
    body = other.save(other.expense("75"), key="shared-key-123")
    assert body["replayed"] is False
    assert other.balance("Cash") == Decimal("-75.00")


def test_missing_idempotency_key_rejected(api):
    r = api.post("/transactions/batch", {"items": [api.expense("10")]})
    assert r.status_code == 422


def test_failed_batch_saves_nothing(api):
    """Atomicity: one bad item → no rows at all."""
    bad = api.expense("10", category="Salary")  # income category on an expense
    r = api.post(
        "/transactions/batch",
        {"items": [api.expense("10"), bad]},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "category_kind_mismatch"
    assert r.json()["error"]["details"] == {"item_index": 1}
    assert api.get("/transactions").json()["total"] == 0


# ------------------------------------------------------------------ validation


@pytest.mark.parametrize(
    "change, code",
    [
        ({"amount": "0"}, "validation_error"),
        ({"amount": "-5"}, "validation_error"),
        ({"amount": "10.999"}, "validation_error"),
        ({"amount": 10.5}, "validation_error"),  # float rejected
        ({"type": "adjustment"}, "validation_error"),  # only via set-balance
        ({"category_id": None}, "category_required"),
    ],
)
def test_invalid_expense_rejected(api, change, code):
    r = api.post(
        "/transactions/batch",
        {"items": [{**api.expense("10"), **change}]},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == code


def test_bangla_digit_amount_accepted(api):
    body = api.save(api.expense("১৫০"))
    assert body["items"][0]["amount"] == "150.00"


def test_future_date_rejected_but_today_and_past_ok(api):
    today = dhaka_today()
    api.save(api.expense("10", occurred_on=today.isoformat()))
    api.save(api.expense("10", occurred_on=(today - timedelta(days=40)).isoformat()))
    r = api.save(api.expense("10", occurred_on=(today + timedelta(days=1)).isoformat()), expect=422)
    assert r["error"]["code"] == "date_in_future"


def test_date_defaults_to_today_in_dhaka(api):
    body = api.save(api.expense("10"))
    assert body["items"][0]["occurred_on"] == dhaka_today().isoformat()


def test_transfer_rules(api):
    bkash = api.new_wallet("bKash")
    same = {"type": "transfer", "amount": "10", "wallet_id": api.cash, "to_wallet_id": api.cash}
    assert api.save(same, expect=422)["error"]["code"] == "transfer_same_wallet"
    no_target = {"type": "transfer", "amount": "10", "wallet_id": api.cash}
    assert api.save(no_target, expect=422)["error"]["code"] == "transfer_needs_target"
    with_cat = {
        "type": "transfer",
        "amount": "10",
        "wallet_id": api.cash,
        "to_wallet_id": bkash,
        "category_id": api.cat["Food & Drinks"],
    }
    assert api.save(with_cat, expect=422)["error"]["code"] == "transfer_has_category"


def test_adjustment_cannot_be_edited_but_can_be_voided(api):
    adj = api.post(f"/wallets/{api.cash}/set-balance", {"balance": "100"}).json()
    r = api.patch(f"/transactions/{adj['id']}", {"amount": "5"})
    assert r.json()["error"]["code"] == "adjustment_not_editable"
    assert api.post(f"/transactions/{adj['id']}/void").status_code == 200
    assert api.balance("Cash") == Decimal("0.00")


def test_voided_transaction_cannot_be_edited(api):
    tx = api.save(api.expense("10"))["items"][0]
    api.post(f"/transactions/{tx['id']}/void")
    r = api.patch(f"/transactions/{tx['id']}", {"amount": "20"})
    assert r.json()["error"]["code"] == "transaction_voided"


# ------------------------------------------------------------------ wallets


def test_wallet_names_unique_case_insensitive(api):
    api.new_wallet("bKash")
    r = api.post("/wallets", {"name": "BKASH", "type": "bkash"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "wallet_name_taken"


def test_switch_default_wallet(api):
    bkash = api.new_wallet("bKash")
    r = api.patch(f"/wallets/{bkash}", {"is_default": True})
    assert r.status_code == 200 and r.json()["is_default"] is True
    wallets = api.wallets()
    assert wallets["Cash"]["is_default"] is False
    assert list(wallets)[0] == "bKash"  # default listed first


def test_archive_rules(api):
    bkash = api.new_wallet("bKash")
    r = api.post(f"/wallets/{api.cash}/archive")
    assert r.json()["error"]["code"] == "cannot_archive_default"

    assert api.post(f"/wallets/{bkash}/archive").status_code == 204
    assert "bKash" not in api.wallets()
    r = api.save(api.expense("10", wallet=bkash), expect=422)
    assert r["error"]["code"] == "wallet_archived"


# ------------------------------------------------------------------ isolation


def test_cannot_use_another_users_wallet_or_category(api, other):
    r = other.save(other.expense("10", wallet=api.cash), expect=404)
    assert r["error"]["code"] == "wallet_not_found"
    foreign_category = {**other.expense("10"), "category_id": api.cat["Food & Drinks"]}
    assert other.save(foreign_category, expect=404)["error"]["code"] == "category_not_found"


def test_cannot_see_or_touch_another_users_transactions(api, other):
    tx = api.save(api.expense("10"))["items"][0]
    assert other.get("/transactions").json()["total"] == 0
    assert other.patch(f"/transactions/{tx['id']}", {"amount": "1"}).status_code == 404
    assert other.post(f"/transactions/{tx['id']}/void").status_code == 404
    assert other.post(f"/wallets/{api.cash}/set-balance", {"balance": "1"}).status_code == 404
    assert other.patch(f"/wallets/{api.cash}", {"name": "Hacked"}).status_code == 404
    assert api.balance("Cash") == Decimal("-10.00")


# ------------------------------------------------------------------ listing


def test_list_filters_and_pagination(api):
    bkash = api.new_wallet("bKash")
    today = dhaka_today()
    last_month = (today.replace(day=1) - timedelta(days=1)).isoformat()
    api.save(
        api.expense("10"),
        api.expense("20", "Transport"),
        api.income("500"),
        api.expense("30", occurred_on=last_month),
        {"type": "transfer", "amount": "40", "wallet_id": api.cash, "to_wallet_id": bkash},
    )
    month = today.strftime("%Y-%m")
    assert api.get("/transactions", params={"month": month}).json()["total"] == 4
    assert api.get("/transactions", params={"type": "expense"}).json()["total"] == 3
    by_cat = api.get("/transactions", params={"category_id": api.cat["Transport"]}).json()
    assert [i["amount"] for i in by_cat["items"]] == ["20.00"]
    # Wallet filter includes transfers INTO the wallet.
    assert api.get("/transactions", params={"wallet_id": bkash}).json()["total"] == 1

    page = api.get("/transactions", params={"limit": 2, "offset": 0}).json()
    assert page["total"] == 5 and len(page["items"]) == 2
    assert api.get("/transactions", params={"month": "2026-13"}).status_code == 422


def test_overview_for_month(api):
    api.save(api.income("20000", "Salary"), api.expense("5000", "Rent"), api.expense("150.50"))
    o = api.get("/analytics/overview").json()
    assert (o["income"], o["expense"], o["net"]) == ("20000.00", "5150.50", "14849.50")
    assert o["transaction_count"] == 3
    assert o["month"] == dhaka_today().strftime("%Y-%m")
