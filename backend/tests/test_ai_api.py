"""/api/v1/ai/message end to end with a FAKE LLM (needs PostgreSQL)."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.ai.llm_client import LLMError, LLMResult
from app.ai.rate_limit import RateLimiter
from app.models import AIInteraction
from tests.conftest import auth_header
from tests.test_ledger import Api

pytestmark = pytest.mark.db


class FakeLLM:
    """Returns canned JSON and records what it was asked."""

    def __init__(self, data=None, error: Exception | None = None) -> None:
        self.data = data or {}
        self.error = error
        self.calls: list[dict] = []

    def generate_json(self, *, system, user, schema, temperature=0.1, audio=None):
        self.calls.append({"system": system, "user": user, "schema": schema})
        if self.error:
            raise self.error
        return LLMResult(self.data, "fake-model", 42, 100, 20)


def record(*items):
    return {"intent": "record", "transactions": list(items)}


def item(amount, desc, category, **kw):
    return {
        "type": "expense",
        "amount": amount,
        "description": desc,
        "category": category,
        "is_planned": False,
        **kw,
    }


@pytest.fixture
def setup(db_client, make_token):
    def _setup(llm: FakeLLM, *, limit: int = 100) -> Api:
        db_client.app.state.llm = llm
        db_client.app.state.ai_rate_limiter = RateLimiter(limit)
        return Api(db_client, make_token())

    return _setup


def send(api: Api, text: str):
    return api.post("/ai/message", {"text": text})


def test_draft_then_confirm_saves_once(setup):
    llm = FakeLLM(
        record(
            item("100", "Rickshaw", "Transport"),
            item("200", "Lunch", "Food & Drinks"),
            item("50", "Tea", "Food & Drinks"),
        )
    )
    api = setup(llm)
    r = send(api, "Ajke 100 taka rickshaw vara, 200 taka lunch, ar ৫০ taka cha")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "transaction_draft"
    draft = body["draft"]
    assert draft["expense_total"] == "350.00"
    assert [i["amount"] for i in draft["items"]] == ["100.00", "200.00", "50.00"]
    assert draft["items"][0]["category"]["name"] == "Transport"
    assert draft["items"][0]["wallet_name"] == "Cash"

    # Nothing saved until confirmed.
    assert api.get("/transactions").json()["total"] == 0
    # The model saw normalized text, inside delimiters.
    assert "ar 50 taka cha" in llm.calls[0]["user"]
    assert llm.calls[0]["user"].startswith("<user_message>")

    # Confirm (twice — simulating a double click): saved exactly once, marked as AI text.
    items = [
        {
            "type": i["type"],
            "amount": i["amount"],
            "wallet_id": i["wallet_id"],
            "category_id": i["category"]["id"],
            "description": i["description"],
            "occurred_on": i["occurred_on"],
        }
        for i in draft["items"]
    ]
    for _ in range(2):
        r = api.post(
            "/transactions/batch",
            {"source": "text", "items": items},
            headers={"Idempotency-Key": draft["draft_id"]},
        )
        assert r.status_code == 201, r.text
    listed = api.get("/transactions").json()
    assert listed["total"] == 3
    assert {t["source"] for t in listed["items"]} == {"text"}
    assert api.balance("Cash") == Decimal("-350.00")


def test_possible_duplicate_is_flagged(setup):
    api = setup(FakeLLM(record(item("200", "Lunch", "Food & Drinks"))))
    api.save(api.expense("200", description="Lunch"))
    issues = send(api, "200 taka lunch").json()["draft"]["items"][0]["issues"]
    assert [i["code"] for i in issues] == ["possible_duplicate"]


def test_budget_intent_points_to_plan_page(setup):
    # Questions are answered by the assistant (see test_assistant.py); budget requests in
    # the quick box are redirected to the dedicated budget planner.
    api = setup(FakeLLM({"intent": "budget", "transactions": []}))
    body = send(api, "Amar jonno ekta budget plan koro").json()
    assert body["kind"] == "unsupported"
    assert "Plan" in body["message"]


def test_missing_amount_asks_for_clarification(setup):
    api = setup(FakeLLM(record(item("", "cha", "Food & Drinks"))))
    body = send(api, "cha kheyechi").json()
    assert body["kind"] == "clarification"
    assert "cha" in body["message"]


def test_ai_failure_returns_friendly_503(setup):
    api = setup(FakeLLM(error=LLMError("down", retryable=True)))
    r = send(api, "50 taka cha")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ai_unavailable"


def test_raw_text_not_stored_unless_opted_in(setup, db_session):
    api = setup(FakeLLM(record(item("50", "Tea", "Food & Drinks"))))
    send(api, "private 50 taka cha")
    logs = db_session.scalars(select(AIInteraction)).all()
    assert len(logs) == 1
    assert logs[0].model == "fake-model" and logs[0].status == "ok"
    assert logs[0].input_text is None  # privacy by default

    api.patch("/me", {"store_ai_text": True})
    send(api, "opted in 50 taka cha")
    texts = {log.input_text for log in db_session.scalars(select(AIInteraction)).all()}
    assert texts == {None, "opted in 50 taka cha"}


def test_rate_limit(setup):
    api = setup(FakeLLM(record(item("50", "Tea", "Food & Drinks"))), limit=2)
    assert send(api, "a 1").status_code == 200
    assert send(api, "a 2").status_code == 200
    r = send(api, "a 3")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


def test_ai_requires_auth_and_config(db_client, make_token):
    assert db_client.post("/api/v1/ai/message", json={"text": "hi"}).status_code == 401
    db_client.app.state.llm = None
    r = db_client.post(
        "/api/v1/ai/message", json={"text": "hi"}, headers=auth_header(make_token(uuid.uuid4()))
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ai_not_configured"


def test_schema_sent_to_llm_lists_only_this_users_categories(setup):
    llm = FakeLLM(record())
    api = setup(llm)
    api.new_wallet("Nagad", "nagad")
    send(api, "test")
    schema = llm.calls[0]["schema"]
    wallets = schema["properties"]["transactions"]["items"]["properties"]["wallet"]["enum"]
    assert sorted(wallets) == ["Cash", "Nagad"]
