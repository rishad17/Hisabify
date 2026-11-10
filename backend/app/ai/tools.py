"""READ-ONLY tools the assistant may call. This registry is the assistant's whole world.

Safety by construction:
  * there is no tool that creates, edits or deletes anything — the LLM cannot change data
  * every handler receives the authenticated user's id from the server, never from the LLM
  * arguments from the LLM are validated; bad arguments return {"error": ...} to the model
  * money is returned as exact decimal strings; the LLM only rephrases these numbers
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai.drafts import parse_amount
from app.core.errors import AppError
from app.models import Category, Transaction, Wallet
from app.services import analytics, ledger, planning, simulator

PERIODS = [
    "today",
    "yesterday",
    "this_week",
    "last_7_days",
    "this_month",
    "last_month",
    "last_30_days",
]


@dataclass
class ToolContext:
    db: Session
    user_id: uuid.UUID


class ToolError(Exception):
    """Bad arguments — reported back to the model so it can correct itself."""


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, (date, uuid.UUID)):
        return str(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


# ------------------------------------------------------------------ helpers


def _today(ctx: ToolContext) -> date:
    return ledger.today_for(ctx.db, ctx.user_id)


def _resolve_period(
    ctx: ToolContext, period: str | None, month: str | None
) -> tuple[date, date, str]:
    """Return [start, end) and a human label. `month` (YYYY-MM) wins over `period`."""
    today = _today(ctx)
    if month:
        try:
            year, mon = (int(x) for x in month.split("-"))
            start = date(year, mon, 1)
        except ValueError as exc:
            raise ToolError("month must look like 2026-11") from exc
        _, end = ledger.month_range(start)
        return start, end, start.strftime("%B %Y")
    period = period or "this_month"
    if period == "today":
        return today, today + timedelta(days=1), "today"
    if period == "yesterday":
        y = today - timedelta(days=1)
        return y, today, "yesterday"
    if period == "this_week":  # week starts Saturday in Bangladesh
        start = today - timedelta(days=(today.weekday() - 5) % 7)
        return start, today + timedelta(days=1), "this week (since Saturday)"
    if period == "last_7_days":
        return today - timedelta(days=6), today + timedelta(days=1), "the last 7 days"
    if period == "last_30_days":
        return today - timedelta(days=29), today + timedelta(days=1), "the last 30 days"
    if period == "last_month":
        start, _ = ledger.month_range(today.replace(day=1) - timedelta(days=1))
        _, end = ledger.month_range(start)
        return start, end, start.strftime("%B %Y")
    if period == "this_month":
        start = today.replace(day=1)
        return start, today + timedelta(days=1), f"{start:%B %Y} so far"
    raise ToolError(f"period must be one of {', '.join(PERIODS)}")


def _category_id(ctx: ToolContext, name: str | None, kind: str | None = None) -> uuid.UUID | None:
    if not name:
        return None
    stmt = select(Category).where(
        Category.user_id == ctx.user_id,
        or_(func.lower(Category.name) == name.strip().lower(), Category.name_bn == name.strip()),
    )
    if kind:
        stmt = stmt.where(Category.kind == kind)
    cat = ctx.db.scalars(stmt).first()
    if cat is None:
        raise ToolError(f'No category named "{name}". Use get_categories to see the list.')
    return cat.id


def _money_arg(raw: Any) -> Decimal:
    value = parse_amount(raw)
    if value is None:
        raise ToolError("amount must be a positive number like 2500")
    return value


# ------------------------------------------------------------------ tools


def get_balances(ctx: ToolContext, **_: Any) -> dict:
    wallets = ledger.list_wallets(ctx.db, ctx.user_id)
    return {
        "wallets": [
            {"name": w.wallet.name, "type": w.wallet.type, "balance": w.balance} for w in wallets
        ],
        "total": sum((w.balance for w in wallets), Decimal("0.00")),
    }


def get_spending(
    ctx: ToolContext,
    period: str | None = None,
    month: str | None = None,
    category: str | None = None,
    **_: Any,
) -> dict:
    start, end, label = _resolve_period(ctx, period, month)
    cat_id = _category_id(ctx, category, "expense") if category else None
    t = Transaction
    base = [
        t.user_id == ctx.user_id,
        t.voided_at.is_(None),
        t.occurred_on >= start,
        t.occurred_on < end,
    ]
    totals = dict(
        ctx.db.execute(
            select(t.type, func.coalesce(func.sum(t.amount), 0))
            .where(*base, t.type.in_(("expense", "income")))
            .group_by(t.type)
        ).all()
    )
    expense_filter = [*base, t.type == "expense"] + ([t.category_id == cat_id] if cat_id else [])
    rows = ctx.db.execute(
        select(Category.name, func.sum(t.amount), func.count())
        .join(Category, Category.id == t.category_id)
        .where(*expense_filter)
        .group_by(Category.name)
        .order_by(func.sum(t.amount).desc())
        .limit(12)
    ).all()
    result = {
        "period": label,
        "from": start,
        "to": end - timedelta(days=1),
        "total_expense": Decimal(totals.get("expense", 0)).quantize(Decimal("0.01")),
        "total_income": Decimal(totals.get("income", 0)).quantize(Decimal("0.01")),
        "by_category": [
            {"category": n, "amount": Decimal(a).quantize(Decimal("0.01")), "transactions": c}
            for n, a, c in rows
        ],
        "note": "Transfers between wallets and balance corrections are not counted.",
    }
    if cat_id:
        result["category_total"] = sum(
            (r["amount"] for r in result["by_category"]), Decimal("0.00")
        )
    return result


def compare_months(ctx: ToolContext, month: str | None = None, **_: Any) -> dict:
    start = _resolve_period(ctx, None, month)[0] if month else _today(ctx).replace(day=1)
    data = analytics.compare(ctx.db, ctx.user_id, start)
    data["items"] = [
        {
            "category": i["category"]["name"],
            "current": i["current"],
            "previous": i["previous"],
            "change": i["change"],
        }
        for i in data["items"]
    ]
    return data


def get_budget_status(ctx: ToolContext, month: str | None = None, **_: Any) -> dict:
    start = _resolve_period(ctx, None, month)[0] if month else _today(ctx).replace(day=1)
    status = planning.budget_status(ctx.db, ctx.user_id, start)
    if status is None:
        return {
            "month": start.strftime("%Y-%m"),
            "budget": None,
            "note": "No budget for this month.",
        }
    status["items"] = [
        {
            "category": i["category"]["name"],
            "budget": i["amount"],
            "spent": i["spent"],
            "remaining": i["remaining"],
            "percent_used": i["percent_used"],
        }
        for i in status["items"]
    ]
    status.pop("explanation", None)
    days_left = (ledger.month_range(start)[1] - _today(ctx)).days
    status["days_left_in_month"] = max(0, days_left)
    return status


def get_safe_to_spend(ctx: ToolContext, **_: Any) -> dict:
    data = planning.safe_to_spend(ctx.db, ctx.user_id)
    # Weekly allowance, computed here so the model never multiplies: per-day amount × days
    # left in this Bangladeshi week (Saturday–Friday), never past the end of the month.
    today = _today(ctx)
    days_to_friday = (4 - today.weekday()) % 7 + 1  # includes today
    week_days = min(days_to_friday, data["days_left"])
    data["days_left_this_week"] = week_days
    data["this_week_allowance"] = (data["per_day"] * week_days).quantize(Decimal("0.01"))
    return data


def simulate_purchase(
    ctx: ToolContext, amount: Any = None, category: str | None = None, **_: Any
) -> dict:
    value = _money_arg(amount)
    cat_id = _category_id(ctx, category, "expense") if category else None
    sim = simulator.simulate_purchase(ctx.db, ctx.user_id, value, cat_id)
    return {**sim.__dict__, "note": "Simulation only — nothing was recorded."}


def get_bills(ctx: ToolContext, **_: Any) -> dict:
    month = _today(ctx).replace(day=1)
    bills = planning.list_bills(ctx.db, ctx.user_id, month)
    expected = planning.list_expected(ctx.db, ctx.user_id, include_closed=False)
    return {
        "bills": [
            {
                "name": b["name"],
                "amount": b["amount"],
                "due_date": b["due_date"],
                "paid": b["paid"],
                "active": b["active"],
            }
            for b in bills
        ],
        "expected_income": [
            {"source": e.source, "amount": e.amount, "expected_on": e.expected_on} for e in expected
        ],
    }


def search_transactions(
    ctx: ToolContext,
    query: str | None = None,
    category: str | None = None,
    period: str | None = None,
    month: str | None = None,
    min_amount: Any = None,
    limit: Any = 10,
    **_: Any,
) -> dict:
    start, end, label = _resolve_period(ctx, period or "last_30_days", month)
    t = Transaction
    stmt = (
        select(t, Category.name, Wallet.name)
        .join(Wallet, Wallet.id == t.wallet_id)
        .outerjoin(Category, Category.id == t.category_id)
        .where(
            t.user_id == ctx.user_id,
            t.voided_at.is_(None),
            t.occurred_on >= start,
            t.occurred_on < end,
        )
    )
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")[:50]
        stmt = stmt.where(t.description.ilike(f"%{escaped}%", escape="\\"))
    if category:
        stmt = stmt.where(t.category_id == _category_id(ctx, category))
    if min_amount not in (None, ""):
        stmt = stmt.where(t.amount >= _money_arg(min_amount))
    try:
        n = max(1, min(20, int(limit)))
    except (TypeError, ValueError):
        n = 10
    rows = ctx.db.execute(stmt.order_by(t.occurred_on.desc(), t.created_at.desc()).limit(n)).all()
    return {
        "period": label,
        "transactions": [
            {
                "date": tx.occurred_on,
                "type": tx.type,
                "amount": tx.amount,
                "description": tx.description,
                "category": cat,
                "wallet": wallet,
            }
            for tx, cat, wallet in rows
        ],
    }


def get_categories(ctx: ToolContext, **_: Any) -> dict:
    cats = ctx.db.scalars(
        select(Category).where(Category.user_id == ctx.user_id, Category.archived_at.is_(None))
    )
    return {"categories": [{"name": c.name, "name_bn": c.name_bn, "kind": c.kind} for c in cats]}


# ------------------------------------------------------------------ registry

_PERIOD = {"type": "STRING", "enum": PERIODS, "description": "Relative period. Default this_month."}
_MONTH = {"type": "STRING", "description": "A specific month as YYYY-MM (overrides period)."}
_CATEGORY = {"type": "STRING", "description": "Category name exactly as in get_categories."}


@dataclass(frozen=True)
class Tool:
    handler: Callable[..., dict]
    declaration: dict[str, Any]


def _decl(
    name: str, description: str, properties: dict | None = None, required: list[str] | None = None
) -> dict:
    decl: dict[str, Any] = {"name": name, "description": description}
    if properties:
        decl["parameters"] = {"type": "OBJECT", "properties": properties}
        if required:
            decl["parameters"]["required"] = required
    return decl


TOOLS: dict[str, Tool] = {
    "get_balances": Tool(
        get_balances, _decl("get_balances", "Current balance of every wallet and the total.")
    ),
    "get_spending": Tool(
        get_spending,
        _decl(
            "get_spending",
            "Total expense and income for a period, with spending by category. Use for "
            "'how much did I spend', 'which category costs most', spending on X.",
            {"period": _PERIOD, "month": _MONTH, "category": _CATEGORY},
        ),
    ),
    "compare_months": Tool(
        compare_months,
        _decl(
            "compare_months",
            "Spending by category this month vs the previous month (same days if the month "
            "is not over). Use for 'compare with last month'.",
            {"month": _MONTH},
        ),
    ),
    "get_budget_status": Tool(
        get_budget_status,
        _decl(
            "get_budget_status",
            "The month's budget per category: budget, spent, remaining, % used.",
            {"month": _MONTH},
        ),
    ),
    "get_safe_to_spend": Tool(
        get_safe_to_spend,
        _decl(
            "get_safe_to_spend",
            "How much the user can still spend this month after reserving unpaid bills, the "
            "savings target and essential budgets; per-day amount; this_week_allowance for "
            "'this week' questions; expected income.",
        ),
    ),
    "simulate_purchase": Tool(
        simulate_purchase,
        _decl(
            "simulate_purchase",
            "What-if: would buying something for `amount` still leave bills, savings and the "
            "budget covered? Records NOTHING. Use for 'can I afford', 'if I buy'.",
            {
                "amount": {"type": "STRING", "description": "Price in taka, digits only"},
                "category": _CATEGORY,
            },
            ["amount"],
        ),
    ),
    "get_bills": Tool(
        get_bills,
        _decl(
            "get_bills",
            "Monthly bills with paid/unpaid status, and expected (not yet received) income.",
        ),
    ),
    "search_transactions": Tool(
        search_transactions,
        _decl(
            "search_transactions",
            "Find individual transactions (newest first, max 20).",
            {
                "query": {
                    "type": "STRING",
                    "description": "Text to look for in the note/description",
                },
                "category": _CATEGORY,
                "period": _PERIOD,
                "month": _MONTH,
                "min_amount": {"type": "STRING", "description": "Only amounts >= this"},
                "limit": {"type": "INTEGER"},
            },
        ),
    ),
    "get_categories": Tool(
        get_categories, _decl("get_categories", "The user's category names (English and Bangla).")
    ),
}


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Unknown tool {name!r}."}
    if not isinstance(args, dict):
        return {"error": "Arguments must be an object."}
    try:
        return jsonable(tool.handler(ctx, **{k: v for k, v in args.items() if isinstance(k, str)}))
    except ToolError as exc:
        return {"error": str(exc)}
    except AppError as exc:  # e.g. "category not found" from a service
        return {"error": exc.message}
