"""Forecast maths + adaptive suggestions (pure) and the approval flow (PostgreSQL)."""

from datetime import datetime, timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from app.services.adjustments import ItemOutlook, suggest
from app.services.forecast import confidence_for, project, typical_daily
from tests.test_ledger import Api

# ------------------------------------------------------------------ pure


def test_typical_daily_ignores_spikes():
    days = [D("100")] * 18 + [D("0")] * 1 + [D("45000")]  # a laptop day
    # 20 days → the top 10% (2 days: the spike + one ৳100 day) are dropped → 1700 / 18
    assert typical_daily(days) == D("94.44")
    assert typical_daily([D("50"), D("150")]) == D("100.00")  # too few days to trim
    assert typical_daily([]) == D("0.00")


def test_projection_and_range():
    p = project(spent=D("3000"), daily=D("200"), remaining_days=10, unpaid_bills=D("1500"))
    assert p.projected == D("6500.00")  # 3000 + 200×10 + 1500
    assert (p.low, p.high) == (D("5900.00"), D("7100.00"))  # ±30% of the future part only
    assert project(D("10"), D("5"), 0, D("0")).projected == D("10.00")


@pytest.mark.parametrize("days, level", [(0, "low"), (13, "low"), (14, "medium"), (60, "good")])
def test_confidence(days, level):
    assert confidence_for(days) == level


def outlook(name, budget, projected, essential=False):
    return ItemOutlook(name, name, D(budget), D(projected), essential)


def test_suggest_moves_room_to_overshooting_category():
    s = suggest(
        [
            outlook("Food", "4000", "4865"),  # needs 870 (rounded up to ৳10)
            outlook("Shopping", "2000", "500"),  # 1500 room
            outlook("Transport", "2000", "1000", essential=True),  # donates last
        ]
    )
    changes = {c["category_name"]: (c["old"], c["new"]) for c in s.changes}
    assert changes == {"Food": ("4000.00", "4870.00"), "Shopping": ("2000.00", "1130.00")}
    assert s.uncovered == 0
    assert "Shopping" in s.reason and "Food" in s.reason


def test_suggest_never_takes_more_than_room_and_reports_shortfall():
    s = suggest([outlook("Food", "1000", "3000"), outlook("Shopping", "500", "300")])
    changes = {c["category_name"]: c["new"] for c in s.changes}
    assert changes == {"Food": "1200.00", "Shopping": "300.00"}  # only its ৳200 of room
    assert s.uncovered == D("1800")
    assert "can't be covered" in s.reason


def test_suggest_nothing_when_on_track():
    assert suggest([outlook("Food", "1000", "900")]) is None


def test_totals_are_preserved():
    items = [outlook("A", "1000", "1500"), outlook("B", "800", "200"), outlook("C", "600", "100")]
    s = suggest(items)
    before = sum(i.budget for i in items)
    after = before + sum(D(c["new"]) - D(c["old"]) for c in s.changes)
    assert after == before  # money is moved, never created


# ------------------------------------------------------------------ database


def today():
    return datetime.now(ZoneInfo("Asia/Dhaka")).date()


@pytest.fixture
def api(db_client, make_token) -> Api:
    return Api(db_client, make_token())


@pytest.fixture
def other(db_client, make_token) -> Api:
    return Api(db_client, make_token())


def save_budget(api: Api, items: dict[str, str], income="20000", savings="0"):
    month = today().strftime("%Y-%m")
    r = api.c.put(
        f"/api/v1/budgets/{month}",
        headers=api.h,
        json={
            "planned_income": income,
            "savings_target": savings,
            "items": [{"category_id": api.cat[n], "amount": a} for n, a in items.items()],
        },
    )
    assert r.status_code == 200, r.text


@pytest.mark.db
def test_forecast_formula_and_confidence(api):
    t = today()
    for i in range(1, 11):  # ৳100 a day for the previous 10 days
        api.save(api.expense("100", occurred_on=(t - timedelta(days=i)).isoformat()))
    f = api.get("/planning/forecast").json()
    assert f["typical_daily"] == "100.00"
    assert f["confidence"] == "low" and f["history_days"] == 10
    expected = D(f["spent_so_far"]) + D("100") * f["remaining_days"] + D(f["unpaid_bills"])
    assert D(f["projected"]) == expected
    assert D(f["low"]) <= D(f["projected"]) <= D(f["high"])
    # Chart series: actual up to today, projection after.
    assert f["series"][t.day - 1]["date"] == t.isoformat()
    assert f["series"][t.day - 1]["actual"] is not None
    assert all(p["actual"] is None for p in f["series"][t.day :])


@pytest.mark.db
def test_alerts(api):
    save_budget(api, {"Food & Drinks": "100", "Transport": "1000"})
    api.save(api.expense("150", "Food & Drinks"), api.expense("850", "Transport"))
    alerts = {a["category"]["name"]: a for a in api.get("/planning/alerts").json()}
    assert alerts["Food & Drinks"]["kind"] == "over"
    assert alerts["Food & Drinks"]["severity"] == "critical"
    assert "৳50 over" in alerts["Food & Drinks"]["message"]
    if api.get("/planning/forecast").json()["remaining_days"] > 0:
        assert alerts["Transport"]["kind"] == "nearly_used"
        assert "85%" in alerts["Transport"]["message"]


@pytest.mark.db
def test_suggest_approve_applies_and_records_history(api):
    save_budget(api, {"Food & Drinks": "10", "Entertainment": "5000"})
    api.save(api.expense("50", "Food & Drinks"))
    r = api.post("/budgets/suggest-adjustment")
    assert r.status_code == 200, r.text
    s = r.json()["suggestion"]
    assert s["status"] == "proposed" and s["proposed_by"] == "system"
    food = next(c for c in s["changes"] if c["category_name"] == "Food & Drinks")
    assert D(food["new"]) >= D("50")

    # Nothing applied yet.
    month = today().strftime("%Y-%m")
    items = {
        i["category"]["name"]: i["amount"]
        for i in api.get(f"/budgets/{month}").json()["budget"]["items"]
    }
    assert items["Food & Drinks"] == "10.00"
    # Asking again returns the same open suggestion (no duplicates).
    assert api.post("/budgets/suggest-adjustment").json()["suggestion"]["id"] == s["id"]

    approved = api.post(f"/budgets/adjustments/{s['id']}/approve").json()
    assert approved["status"] == "approved" and approved["decided_at"]
    budget = api.get(f"/budgets/{month}").json()["budget"]
    items = {i["category"]["name"]: D(i["amount"]) for i in budget["items"]}
    assert items["Food & Drinks"] == D(food["new"])
    assert sum(items.values()) == D("5010")  # money moved, not created

    again = api.post(f"/budgets/adjustments/{s['id']}/approve")
    assert again.json()["error"]["code"] == "adjustment_closed"
    history = api.get(f"/budgets/{month}/adjustments").json()
    assert [h["status"] for h in history] == ["approved"]


@pytest.mark.db
def test_stale_suggestion_cannot_be_approved_and_manual_edits_are_logged(api):
    save_budget(api, {"Food & Drinks": "10", "Entertainment": "5000"})
    api.save(api.expense("50", "Food & Drinks"))
    s = api.post("/budgets/suggest-adjustment").json()["suggestion"]
    save_budget(api, {"Food & Drinks": "20", "Entertainment": "4990"})  # user edits meanwhile
    r = api.post(f"/budgets/adjustments/{s['id']}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "budget_changed"

    month = today().strftime("%Y-%m")
    history = api.get(f"/budgets/{month}/adjustments").json()
    manual = next(h for h in history if h["proposed_by"] == "user")
    assert manual["status"] == "approved"
    assert {c["category_name"]: (c["old"], c["new"]) for c in manual["changes"]} == {
        "Entertainment": ("5000.00", "4990.00"),
        "Food & Drinks": ("10.00", "20.00"),
    }
    rejected = api.post(f"/budgets/adjustments/{s['id']}/reject").json()
    assert rejected["status"] == "rejected"


@pytest.mark.db
def test_nothing_to_suggest_and_isolation(api, other):
    save_budget(api, {"Entertainment": "5000"})
    body = api.post("/budgets/suggest-adjustment").json()
    assert body["suggestion"] is None and "on track" in body["message"]
    save_budget(api, {"Food & Drinks": "10"})
    api.save(api.expense("500", "Food & Drinks"))
    body = api.post("/budgets/suggest-adjustment").json()
    assert body["suggestion"] is None and "can't be covered" in body["message"]

    # Another user can't see or decide on these.
    save_budget(api, {"Food & Drinks": "10", "Entertainment": "5000"})
    s = api.post("/budgets/suggest-adjustment").json()["suggestion"]
    assert other.post(f"/budgets/adjustments/{s['id']}/approve").status_code == 404
    assert other.get(f"/budgets/{today().strftime('%Y-%m')}/adjustments").json() == []
