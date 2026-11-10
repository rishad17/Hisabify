"""Assistant (function calling) + purchase simulator endpoint (needs PostgreSQL)."""

import uuid
from decimal import Decimal as D

import pytest
from sqlalchemy import func, select

from app.ai.llm_client import LLMError, LLMResult, TurnResult
from app.ai.rate_limit import RateLimiter
from app.ai.tools import TOOLS, ToolContext, run_tool
from app.models import Transaction
from tests.test_ledger import Api

pytestmark = pytest.mark.db


class ScriptedLLM:
    """Plays back a script of turns: ("call", [(name, args), ...]) or ("text", "answer")."""

    def __init__(self, script, extraction=None, error=None):
        self.script = list(script)
        self.extraction = extraction or {"intent": "question", "transactions": []}
        self.error = error
        self.turns: list[dict] = []

    def generate_json(self, **kwargs):
        return LLMResult(self.extraction, "fake", 1, 1, 1)

    def generate_turn(
        self, *, system, contents, tools, temperature=0.2, model=None, allow_tools=True
    ):
        self.turns.append(
            {"contents": list(contents), "tools": tools, "allow_tools": allow_tools, "model": model}
        )
        if self.error:
            raise self.error
        kind, value = self.script.pop(0) if self.script else ("text", "done")
        if kind == "call" and allow_tools:
            parts = [{"functionCall": {"name": n, "args": a}} for n, a in value]
            return TurnResult(
                {"role": "model", "parts": parts}, list(value), "", "fake-model", 5, 10, 5
            )
        text = value if kind == "text" else "Here is what I found."
        return TurnResult(
            {"role": "model", "parts": [{"text": text}]}, [], text, "fake-model", 5, 10, 5
        )


@pytest.fixture
def api(db_client, make_token) -> Api:
    return Api(db_client, make_token())


@pytest.fixture
def other(db_client, make_token) -> Api:
    return Api(db_client, make_token())


def ask(db_client, api: Api, llm, text="How much did I spend this month?", history=None):
    db_client.app.state.llm = llm
    db_client.app.state.ai_rate_limiter = RateLimiter(100)
    return api.post("/ai/ask", {"text": text, "history": history or []})


def test_answer_uses_real_numbers_from_tools(db_client, api):
    api.save(
        api.expense("200", "Food & Drinks"), api.expense("100", "Transport"), api.income("5000")
    )
    llm = ScriptedLLM(
        [("call", [("get_spending", {"period": "this_month"})]), ("text", "You spent ৳300.")]
    )
    r = ask(db_client, api, llm)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "You spent ৳300."
    [used] = body["tools_used"]
    assert used["name"] == "get_spending"
    assert used["result"]["total_expense"] == "300.00"
    assert used["result"]["total_income"] == "5000.00"
    assert [c["category"] for c in used["result"]["by_category"]] == ["Food & Drinks", "Transport"]
    # The tool result was sent back to the model as a functionResponse.
    second_call_contents = llm.turns[1]["contents"]
    assert second_call_contents[-1]["parts"][0]["functionResponse"]["name"] == "get_spending"
    assert llm.turns[1]["model"] == "fake-model"  # stays on the same model


def test_tools_only_see_the_signed_in_user(db_client, api, other):
    api.save(api.expense("999"))
    llm = ScriptedLLM([("call", [("get_spending", {}), ("get_balances", {})]), ("text", "ok")])
    used = ask(db_client, other, llm).json()["tools_used"]
    assert used[0]["result"]["total_expense"] == "0.00"
    assert used[1]["result"]["total"] == "0.00"


def test_no_tool_can_write(db_session, api):
    """Run every registered tool; the number of transactions must not change."""
    api.save(api.expense("50"))
    user_id = uuid.UUID(api.get("/me").json()["profile"]["id"])
    count = lambda: db_session.scalar(select(func.count()).select_from(Transaction))  # noqa: E731
    before = count()
    ctx = ToolContext(db_session, user_id)
    for name in TOOLS:
        args = {"amount": "100"} if name == "simulate_purchase" else {}
        assert "error" not in run_tool(ctx, name, args), name
    assert count() == before
    assert all(n.split("_")[0] in {"get", "compare", "simulate", "search"} for n in TOOLS)


def test_bad_tool_calls_are_reported_not_crashed(db_client, api):
    llm = ScriptedLLM(
        [
            ("call", [("delete_everything", {}), ("simulate_purchase", {"amount": "abc"})]),
            (
                "call",
                [
                    ("get_spending", {"period": "next_century"}),
                    ("get_spending", {"category": "Nope"}),
                ],
            ),
            ("text", "Sorry."),
        ]
    )
    used = ask(db_client, api, llm).json()["tools_used"]
    errors = [u["result"].get("error", "") for u in used]
    assert "Unknown tool" in errors[0]
    assert "amount" in errors[1]
    assert "period" in errors[2]
    assert "No category" in errors[3]


def test_last_round_forces_an_answer(db_client, api):
    llm = ScriptedLLM([("call", [("get_balances", {})])] * 10)
    body = ask(db_client, api, llm).json()
    assert len(body["tools_used"]) == 3  # MAX_ROUNDS
    assert llm.turns[-1]["allow_tools"] is False
    assert body["answer"]


def test_history_is_passed_for_follow_ups(db_client, api):
    llm = ScriptedLLM([("text", "Last month you spent ৳0.")])
    ask(
        db_client,
        api,
        llm,
        text="and last month?",
        history=[
            {"role": "user", "text": "how much this month?"},
            {"role": "assistant", "text": "৳300"},
        ],
    )
    roles = [c["role"] for c in llm.turns[0]["contents"]]
    assert roles == ["user", "model", "user"]


def test_simulation_via_assistant_records_nothing(db_client, api):
    api.save(api.income("10000"))
    llm = ScriptedLLM([("call", [("simulate_purchase", {"amount": "2500"})]), ("text", "Yes.")])
    used = ask(db_client, api, llm, text="Can I buy a 2500 taka keyboard?").json()["tools_used"]
    assert used[0]["result"]["verdict"] == "likely_affordable"  # no budget → never "affordable"
    assert used[0]["result"]["available_after"] == "7500.00"
    assert api.get("/transactions").json()["total"] == 1


def test_llm_failure_is_friendly(db_client, api):
    r = ask(db_client, api, ScriptedLLM([], error=LLMError("down", retryable=True)))
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_unavailable"


def test_quick_entry_routes_questions_to_assistant(db_client, api):
    db_client.app.state.llm = ScriptedLLM(
        [("call", [("get_balances", {})]), ("text", "You have ৳0.")]
    )
    db_client.app.state.ai_rate_limiter = RateLimiter(100)
    body = api.post("/ai/message", {"text": "amar koto taka ache?"}).json()
    assert body["kind"] == "answer"
    assert body["answer"] == "You have ৳0."
    assert body["tools_used"][0]["name"] == "get_balances"


def test_search_transactions_escapes_wildcards(db_client, api):
    api.save(api.expense("10", description="100% juice"), api.expense("20", description="tea"))
    user_id = uuid.UUID(api.get("/me").json()["profile"]["id"])
    from app.core.db import get_db

    db = next(db_client.app.dependency_overrides[get_db]())
    found = run_tool(ToolContext(db, user_id), "search_transactions", {"query": "%"})
    assert [t["description"] for t in found["transactions"]] == ["100% juice"]


# ------------------------------------------------------------------ simulator endpoint


def test_simulate_endpoint(api):
    api.save(api.income("20000", "Salary"))
    r = api.post("/planning/simulate", {"amount": "25000"})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["verdict"] == "not_affordable"
    assert s["available_after"] == "-5000.00"
    assert D(s["max_without_touching_savings"]) == D("20000")
    assert api.get("/transactions").json()["total"] == 1  # nothing recorded
    bad = api.post("/planning/simulate", {"amount": "0"})
    assert bad.status_code == 422


# ------------------------------------------------------------------ grounding


def test_wrong_number_is_corrected(db_client, api):
    api.save(api.income("1000"))
    llm = ScriptedLLM(
        [
            ("call", [("get_balances", {})]),
            ("text", "You have ৳1,100."),  # copying slip
            ("text", "You have ৳1,000."),  # corrected after the grounding check
        ]
    )
    body = ask(db_client, api, llm, text="koto taka ache?").json()
    assert body["answer"] == "You have ৳1,000."
    assert "not in the tool results: ৳1,100" in llm.turns[-1]["contents"][-1]["parts"][0]["text"]


def test_still_wrong_number_is_flagged(db_client, api):
    api.save(api.income("1000"))
    llm = ScriptedLLM(
        [("call", [("get_balances", {})]), ("text", "You have ৳1,100."), ("text", "Still ৳1,100.")]
    )
    body = ask(db_client, api, llm).json()
    assert body["answer"].startswith("Still ৳1,100.")
    assert "couldn't verify some numbers" in body["answer"]
