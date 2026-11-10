"""Security headers, data export and deletion."""

import uuid

import pytest

from tests.conftest import auth_header
from tests.test_ledger import Api


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in r.headers["content-security-policy"]


@pytest.mark.db
def test_delete_requires_typed_confirmation(db_client, make_token):
    h = auth_header(make_token())
    db_client.get("/api/v1/me", headers=h)
    for body in ({}, {"confirm": "yes"}, {"confirm": "delete"}):
        r = db_client.request("DELETE", "/api/v1/me/data", headers=h, json=body)
        assert r.status_code == 422
    assert db_client.get("/api/v1/me", headers=h).json()["is_new_user"] is False  # untouched


def test_account_deletion_needs_server_key(client, make_token):
    r = client.request(
        "DELETE", "/api/v1/me", headers=auth_header(make_token()), json={"confirm": "DELETE"}
    )
    assert r.json()["error"]["code"] == "account_deletion_not_configured"


@pytest.fixture
def api(db_client, make_token) -> Api:
    return Api(db_client, make_token())


@pytest.fixture
def other(db_client, make_token) -> Api:
    return Api(db_client, make_token())


@pytest.mark.db
def test_wipe_everything_then_fresh_start(api, other):
    # Build up data touching every table with RESTRICT links.
    bkash = api.new_wallet("bKash")
    api.save(api.expense("100"), api.income("5000"))
    api.save({"type": "transfer", "amount": "50", "wallet_id": api.cash, "to_wallet_id": bkash})
    bill = api.post(
        "/bills", {"name": "Rent", "amount": "10", "category_id": api.cat["Rent"], "due_day": 1}
    ).json()
    api.post(f"/bills/{bill['id']}/pay", {}, headers={"Idempotency-Key": uuid.uuid4().hex})
    month = api.get("/analytics/overview").json()["month"]
    api.c.put(
        f"/api/v1/budgets/{month}",
        headers=api.h,
        json={"planned_income": "100", "items": [{"category_id": api.cat["Rent"], "amount": "10"}]},
    )
    other.save(other.expense("777"))

    r = api.c.request("DELETE", "/api/v1/me/data", headers=api.h, json={"confirm": "DELETE"})
    assert r.status_code == 204, r.text

    me = api.get("/me").json()
    assert me["is_new_user"] is True  # fresh default setup
    assert api.get("/transactions").json()["total"] == 0
    assert list(api.wallets()) == ["Cash"]
    assert api.get("/bills").json() == []
    assert api.get(f"/budgets/{month}").json() == {"budget": None}
    # The other user is untouched.
    assert other.get("/transactions").json()["total"] == 1


@pytest.mark.db
def test_csv_export(api, other):
    api.save(
        api.expense("120.50", "Transport", description="=HYPERLINK(evil)"),
        api.expense("50", description="চা"),
    )
    other.save(other.expense("999", description="not mine"))
    r = api.get("/me/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "date,type,amount,wallet,to_wallet,category,description,source"
    assert len(lines) == 3
    assert "'=HYPERLINK(evil)" in text  # formula injection neutralised
    assert "চা" in text and "not mine" not in text


@pytest.mark.db
def test_demo_seed_produces_consistent_data(db_session, api):
    from decimal import Decimal

    from app.services.demo_seed import DemoSeedError, seed_demo

    user_id = uuid.UUID(api.get("/me").json()["profile"]["id"])
    result = seed_demo(db_session, user_id)
    assert result["transactions"] > 60
    wallets = api.wallets()
    assert set(wallets) == {"Cash", "bKash", "Bank"}
    # Derived balances equal opening balances + history (sanity: total matches overview).
    total = sum(Decimal(w["balance"]) for w in wallets.values())
    assert Decimal(api.get("/analytics/overview").json()["total_balance"]) == total
    month = api.get("/analytics/overview").json()["month"]
    budget = api.get(f"/budgets/{month}").json()["budget"]
    assert budget is not None and budget["planned_income"] == "26000.00"
    assert api.get("/expected-incomes").json()[0]["amount"] == "15000.00"
    with pytest.raises(DemoSeedError):
        seed_demo(db_session, user_id)  # never seeds over existing data
