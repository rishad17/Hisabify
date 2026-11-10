"""Chart aggregates (needs PostgreSQL)."""

from datetime import date, datetime, timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from tests.test_ledger import Api

pytestmark = pytest.mark.db


def today() -> date:
    return datetime.now(ZoneInfo("Asia/Dhaka")).date()


def prev_month_day(day: int) -> date | None:
    first_this = today().replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.replace(day=day) if day <= last_prev.day else None


@pytest.fixture
def api(db_client, make_token) -> Api:
    return Api(db_client, make_token())


@pytest.fixture
def other(db_client, make_token) -> Api:
    return Api(db_client, make_token())


def test_breakdown_sorted_shares_and_only_expenses(api):
    bkash = api.new_wallet("bKash")
    api.save(
        api.expense("300", "Food & Drinks"),
        api.expense("100", "Transport"),
        api.expense("100", "Groceries"),
        api.income("9999", "Salary"),
        {"type": "transfer", "amount": "5000", "wallet_id": api.cash, "to_wallet_id": bkash},
    )
    voided = api.save(api.expense("777", "Shopping"))["items"][0]
    api.post(f"/transactions/{voided['id']}/void")
    api.post(f"/wallets/{api.cash}/set-balance", {"balance": "1"})  # adjustment ignored

    b = api.get("/analytics/category-breakdown").json()
    assert b["total"] == "500.00"
    assert [(i["category"]["name"], i["amount"], i["share_percent"]) for i in b["items"]] == [
        ("Food & Drinks", "300.00", 60.0),
        ("Groceries", "100.00", 20.0),
        ("Transport", "100.00", 20.0),
    ]


def test_breakdown_folds_small_categories_into_other(api):
    names = [
        "Food & Drinks", "Groceries", "Transport", "Rent", "Bills & Utilities",
        "Mobile & Internet", "Education", "Healthcare", "Shopping",
    ]  # fmt: skip
    api.save(*[api.expense(str(100 * (len(names) - i)), n) for i, n in enumerate(names)])
    items = api.get("/analytics/category-breakdown").json()["items"]
    assert len(items) == 8
    other = items[-1]
    assert other["category"] is None and other["other_count"] == 2
    assert other["amount"] == "300.00"  # 200 + 100


def test_daily_is_zero_filled_up_to_today(api):
    t = today()
    api.save(api.expense("50"), api.income("200"))
    d = api.get("/analytics/daily").json()
    assert len(d["days"]) == t.day == d["days_counted"]
    assert d["days"][0]["date"] == t.replace(day=1).isoformat()
    last = d["days"][-1]
    assert (last["date"], last["expense"], last["income"]) == (t.isoformat(), "50.00", "200.00")
    assert D(d["average_daily_expense"]) == (D("50") / t.day).quantize(D("0.01"))


def test_daily_for_past_month_covers_whole_month(api):
    d = api.get("/analytics/daily", params={"month": "2026-02"}).json()
    assert len(d["days"]) == 28 and d["total_expense"] == "0.00"


def test_monthly_income_vs_expense(api):
    p = prev_month_day(1)
    api.save(
        api.income("10000", "Salary", occurred_on=p.isoformat()),
        api.expense("2500", occurred_on=p.isoformat()),
    )
    api.save(api.expense("100"))
    months = api.get("/analytics/monthly", params={"months": 3}).json()["months"]
    assert len(months) == 3
    assert months[-1]["partial"] is True and months[-1]["expense"] == "100.00"
    assert (months[-2]["income"], months[-2]["expense"], months[-2]["net"]) == (
        "10000.00",
        "2500.00",
        "7500.00",
    )
    assert months[0]["income"] == "0.00"  # zero-filled


def test_compare_uses_same_days_for_current_month(api):
    t = today()
    inside = prev_month_day(1)
    api.save(api.expense("400", occurred_on=inside.isoformat()))
    outside = prev_month_day(t.day + 1)
    if outside:  # later in last month than today's date → excluded from a fair comparison
        api.save(api.expense("9000", occurred_on=outside.isoformat()))
    api.save(api.expense("100"), api.expense("70", "Transport"))

    c = api.get("/analytics/compare").json()
    assert c["partial"] is True
    assert (c["current_total"], c["previous_total"], c["change"]) == ("170.00", "400.00", "-230.00")
    food = next(i for i in c["items"] if i["category"]["name"] == "Food & Drinks")
    assert (food["current"], food["previous"]) == ("100.00", "400.00")


def test_compare_past_month_is_full(api):
    p1, p_last = prev_month_day(1), today().replace(day=1) - timedelta(days=1)
    api.save(
        api.expense("10", occurred_on=p1.isoformat()),
        api.expense("20", occurred_on=p_last.isoformat()),
    )
    month = p1.strftime("%Y-%m")
    c = api.get("/analytics/compare", params={"month": month}).json()
    assert c["partial"] is False and c["current_total"] == "30.00"


def test_analytics_are_per_user(api, other):
    api.save(api.expense("500"))
    assert other.get("/analytics/category-breakdown").json()["total"] == "0.00"
    assert other.get("/analytics/compare").json()["items"] == []
    assert all(d["expense"] == "0.00" for d in other.get("/analytics/daily").json()["days"])
