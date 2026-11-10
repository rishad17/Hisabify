"""Score the REAL model on tests/ai_eval/cases.py.

    cd backend
    python -m tests.ai_eval.run_eval              # uses GEMINI_API_KEY from .env
    python -m tests.ai_eval.run_eval --model gemini-3.1-flash-lite

Not part of CI (needs a key and costs quota). Re-run after changing the prompt and keep
the score in the README.
"""

import argparse
import sys
import time
import uuid
from datetime import date

from app.ai.drafts import build_draft
from app.ai.extraction import CategoryInfo, WalletInfo, extract
from app.ai.llm_client import GeminiClient, LLMError
from app.ai.normalize import normalize_user_text
from app.core.config import Settings
from app.services.onboarding import DEFAULT_CATEGORIES
from tests.ai_eval.cases import CASES

TODAY = date(2026, 11, 11)
CATEGORIES = [
    CategoryInfo(uuid.uuid4(), c.name, c.name_bn, c.kind, c.icon) for c in DEFAULT_CATEGORIES
]
WALLETS = [
    WalletInfo(uuid.uuid4(), "Cash", "cash", True),
    WalletInfo(uuid.uuid4(), "bKash", "bkash", False),
    WalletInfo(uuid.uuid4(), "Nagad", "nagad", False),
    WalletInfo(uuid.uuid4(), "Bank", "bank", False),
]


def check(case: dict, draft) -> list[str]:
    problems: list[str] = []
    got = [
        (
            i.type,
            f"{i.amount.normalize():f}",
            i.category.name if i.category else None,
            i.occurred_on.isoformat(),
            i.wallet.name if i.wallet else None,
            i.to_wallet.name if i.to_wallet else None,
        )
        for i in draft.items
    ]
    expected = case["expect"]
    if len(got) != len(expected):
        problems.append(f"expected {len(expected)} items, got {len(got)}: {got}")
    for exp, g in zip(expected, got, strict=False):
        etype, eamount, ecat, extra = exp
        if (g[0], g[1]) != (etype, eamount):
            problems.append(f"expected {etype} {eamount}, got {g[0]} {g[1]}")
        if ecat is not None and g[2] != ecat:
            problems.append(f"category: expected {ecat}, got {g[2]}")
        if "date" in extra and g[3] != extra["date"]:
            problems.append(f"date: expected {extra['date']}, got {g[3]}")
        if "wallet" in extra and g[4] != extra["wallet"]:
            problems.append(f"wallet: expected {extra['wallet']}, got {g[4]}")
        if "to_wallet" in extra and g[5] != extra["to_wallet"]:
            problems.append(f"to_wallet: expected {extra['to_wallet']}, got {g[5]}")
    if len(draft.planned) != case.get("planned", 0):
        problems.append(f"planned: expected {case.get('planned', 0)}, got {len(draft.planned)}")
    if case.get("clarify") and not draft.clarifications:
        problems.append("expected a clarification question")
    if "intent" in case and draft.intent != case["intent"]:
        problems.append(f"intent: expected {case['intent']}, got {draft.intent}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between calls")
    args = parser.parse_args()

    settings = Settings()
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set")
        return 2
    llm = GeminiClient(
        settings.gemini_api_key,
        args.model or settings.gemini_model,
        None if args.model else settings.gemini_fallback_model,
        timeout_seconds=30,
    )

    passed, latencies, models = 0, [], set()
    for n, case in enumerate(CASES, 1):
        try:
            result = extract(
                llm,
                text=normalize_user_text(case["text"]),
                today=TODAY,
                categories=CATEGORIES,
                wallets=WALLETS,
                language="en",
            )
            draft = build_draft(result.data, categories=CATEGORIES, wallets=WALLETS, today=TODAY)
            problems = check(case, draft)
            latencies.append(result.latency_ms)
            models.add(result.model)
        except LLMError as exc:
            problems = [f"LLM error: {exc}"]
        ok = not problems
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'} {n:2}. {case['text']}")
        for p in problems:
            print(f"        - {p}")
        time.sleep(args.delay)

    total = len(CASES)
    avg = sum(latencies) / len(latencies) if latencies else 0
    score = f"{passed}/{total} ({passed / total:.0%})"
    print(f"\nScore: {score}  avg latency {avg:.0f} ms  models {sorted(models)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
