"""Live check of the assistant against the REAL model with FIXED tool data (no database).

    cd backend && python -m tests.ai_eval.assistant_eval

Checks: the right tool is chosen, the answer quotes the tools' numbers (not invented
ones), affordability questions go through simulate_purchase, and the reply language
follows the question. Not part of CI (needs a key).
"""

import re
import sys
import time
from datetime import date
from unittest import mock

from app.ai import assistant
from app.ai.llm_client import LLMError
from app.main import create_app

FIXTURES = {
    "get_balances": {
        "wallets": [
            {"name": "Cash", "type": "cash", "balance": "3250.00"},
            {"name": "bKash", "type": "bkash", "balance": "8740.50"},
        ],
        "total": "11990.50",
    },
    "get_spending": {
        "period": "November 2026 so far",
        "total_expense": "18450.50",
        "total_income": "25000.00",
        "by_category": [
            {"category": "Rent", "amount": "8000.00", "transactions": 1},
            {"category": "Food & Drinks", "amount": "4230.50", "transactions": 23},
            {"category": "Groceries", "amount": "2600.00", "transactions": 5},
        ],
        "note": "Transfers between wallets and balance corrections are not counted.",
    },
    "compare_months": {
        "partial": True,
        "current_label": "1 Nov–11 Nov",
        "previous_label": "1 Oct–11 Oct",
        "current_total": "18450.50",
        "previous_total": "16120.00",
        "change": "2330.50",
        "items": [
            {
                "category": "Food & Drinks",
                "current": "4230.50",
                "previous": "3100.00",
                "change": "1130.50",
            },
            {"category": "Shopping", "current": "0.00", "previous": "800.00", "change": "-800.00"},
        ],
    },
    "get_safe_to_spend": {
        "days_left": 20,
        "available": "6200.00",
        "recommended": "4100.00",
        "per_day": "205.00",
        "days_left_this_week": 3,
        "this_week_allowance": "615.00",
        "flexible_budget_left": "4100.00",
        "unpaid_bills": "1200.00",
        "savings_to_reserve": "3000.00",
        "expected_income": "0.00",
        "confidence": "good",
        "notes": [],
    },
    "simulate_purchase": {
        "amount": "2500.00",
        "verdict": "over_budget",
        "available_after": "3700.00",
        "savings_shortfall": "0.00",
        "category_name": "Shopping",
        "category_remaining_after": "-1000.00",
        "reasons": [
            "After buying, ৳3,700 stays free after bills, savings and essentials.",
            "It puts Shopping ৳1,000 over its budget.",
        ],
        "alternatives": ["Spend up to ৳1,500 within your Shopping budget."],
        "note": "Simulation only — nothing was recorded.",
    },
    "get_forecast": {
        "spent_so_far": "18470.00",
        "typical_daily": "640.00",
        "remaining_days": 19,
        "unpaid_bills": "1200.00",
        "projected": "31830.00",
        "projected_still_to_spend": "13360.00",
        "low": "28182.00",
        "high": "35478.00",
        "budget_total": "30000.00",
        "confidence": "low",
        "alerts": ["At your usual pace, Groceries will be about ৳900 over budget by month end."],
        "note": "Estimate only: typical daily spending × days left + unpaid bills.",
    },
    "get_budget_status": {
        "month": "2026-11",
        "items": [
            {
                "category": "Food & Drinks",
                "budget": "4000.00",
                "spent": "4230.50",
                "remaining": "-230.50",
                "percent_used": 105,
            },
            {
                "category": "Transport",
                "budget": "2000.00",
                "spent": "1520.00",
                "remaining": "480.00",
                "percent_used": 76,
            },
        ],
        "days_left_in_month": 20,
    },
}

# (question, tools that must be called, numbers the answer must contain, expected script)
CASES = [
    ("How much did I spend this month?", {"get_spending"}, ["18,450"], "latin"),
    ("Which category costs me the most?", {"get_spending"}, ["Rent", "8,000"], "latin"),
    ("Amar total koto taka ache?", {"get_balances"}, ["11,990"], "latin"),
    ("এই মাসে আমি কত খরচ করেছি?", {"get_spending"}, None, "bangla"),
    ("Compare this month with last month", {"compare_months"}, ["2,330"], "latin"),
    ("How much can I spend this week?", {"get_safe_to_spend"}, ["615"], "latin"),
    (
        "If I buy headphones for 2500 taka, can I still save this month?",
        {"simulate_purchase"},
        ["1,000"],
        "latin",
    ),
    ("Am I over budget anywhere?", {"get_budget_status"}, ["Food"], "latin"),
    ("Month end e amar koto khoroch hobe?", {"get_forecast"}, ["31,830"], "latin"),
    ("How much more will I spend before the month ends?", {"get_forecast"}, ["13,360"], "latin"),
    ("Delete all my transactions", set(), None, "latin"),
]


class FakeDB:
    def get(self, *a, **k):
        return None

    def add(self, *a, **k):
        pass

    def commit(self):
        pass


def main() -> int:
    llm = create_app().state.llm
    passed = 0
    for question, must_call, must_contain, script in CASES:
        called: list[str] = []

        def fake_run_tool(ctx, name, args, _called=called):
            _called.append(name)
            return FIXTURES.get(name, {"error": f"Unknown tool {name!r}."})

        with (
            mock.patch.object(assistant, "run_tool", fake_run_tool),
            mock.patch.object(assistant, "today_for", lambda db, uid: date(2026, 11, 11)),
        ):
            for attempt in range(3):
                try:
                    reply = assistant.answer_question(FakeDB(), None, question, llm=llm)
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == 2 or not isinstance(getattr(exc, "__cause__", None), LLMError):
                        reply = {"answer": f"ERROR {exc}"}
                        break
                    time.sleep(5)

        answer = reply["answer"]
        problems = []
        if must_call and not must_call & set(called):
            problems.append(f"expected a call to {must_call}, got {called}")
        if not must_call and called and question.startswith("Delete"):
            pass  # reading data first is fine; it must just not claim to delete
        for needle in must_contain or []:
            if needle not in answer:
                problems.append(f"answer lacks {needle!r}")
        # U+09F3 (৳) is in the Bengali block too, so exclude it from the check.
        has_bangla = bool(re.search(r"[ঀ-৲৴-৿]", answer))
        if script == "bangla" and not has_bangla:
            problems.append("expected a Bangla-script answer")
        if script == "latin" and has_bangla:
            problems.append("expected a Latin-script answer")
        if question.startswith("Delete") and re.search(r"\b(deleted|removed)\b", answer, re.I):
            problems.append("claimed to delete data")
        ok = not problems
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {question}")
        print(f"      tools: {called}")
        print(f"      answer: {answer[:220]!r}")
        for p in problems:
            print(f"      - {p}")
        time.sleep(2)
    print(f"\nScore: {passed}/{len(CASES)}")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
