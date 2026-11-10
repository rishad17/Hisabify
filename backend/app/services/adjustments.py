"""Adaptive budget suggestions with explicit approval and a full change history.

  forecast says Food will overshoot by ৳900
      → suggest: move ৳900 from categories projected to have room (non-essential first)
      → saved as a PROPOSED budget_adjustment — the budget itself is untouched
      → user approves  → amounts applied (only if the budget hasn't changed meanwhile)
        user rejects   → kept as history, nothing applied

Manual edits in the budget editor are recorded too (proposed_by="user", approved).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Budget, BudgetAdjustment, BudgetItem, Category
from app.services import forecast as fc
from app.services.budget_engine import taka

ZERO = Decimal("0.00")
STEP = Decimal("10")


# ------------------------------------------------------------------ pure suggestion


@dataclass
class ItemOutlook:
    category_id: Any
    name: str
    budget: Decimal
    projected: Decimal
    is_essential: bool


@dataclass
class Suggestion:
    changes: list[dict[str, Any]]  # {category_id, category_name, old, new}
    reason: str
    uncovered: Decimal


def suggest(items: list[ItemOutlook]) -> Suggestion | None:
    """Move budget from categories with projected room to those projected to overshoot.

    Never moves more than a donor's projected room; essential categories donate last.
    Returns None when nothing is projected to go over.
    """
    needs = {
        i.category_id: ((i.projected - i.budget) / STEP).to_integral_value(rounding=ROUND_UP) * STEP
        for i in items
        if i.projected > i.budget
    }
    if not needs:
        return None
    donors = sorted(
        (i for i in items if i.category_id not in needs and i.budget > i.projected),
        key=lambda i: (i.is_essential, -(i.budget - i.projected)),
    )
    room = {
        d.category_id: ((d.budget - d.projected) / STEP).to_integral_value(rounding=ROUND_DOWN)
        * STEP
        for d in donors
    }
    by_id = {i.category_id: i for i in items}
    new_amounts = {i.category_id: i.budget for i in items}
    moves: list[str] = []
    uncovered = ZERO

    for need_id, need in sorted(needs.items(), key=lambda kv: -kv[1]):
        remaining = need
        for d in donors:
            if remaining <= 0:
                break
            give = min(room[d.category_id], remaining)
            if give <= 0:
                continue
            room[d.category_id] -= give
            new_amounts[d.category_id] -= give
            new_amounts[need_id] += give
            remaining -= give
            moves.append(f"{taka(give)} from {d.name} to {by_id[need_id].name}")
        uncovered += remaining

    changes = [
        {
            "category_id": str(cid),
            "category_name": by_id[cid].name,
            "old": f"{by_id[cid].budget:.2f}",
            "new": f"{amount:.2f}",
        }
        for cid, amount in new_amounts.items()
        if amount != by_id[cid].budget
    ]
    over = ", ".join(f"{by_id[c].name} (+{taka(n)})" for c, n in needs.items())
    reason = f"At your current pace these will overshoot: {over}."
    if moves:
        reason += " Suggested: move " + "; ".join(moves) + "."
    if uncovered > 0:
        reason += (
            f" {taka(uncovered)} can't be covered by other categories — consider spending less "
            "or lowering this month's savings target."
        )
    return Suggestion(changes, reason, uncovered)


# ------------------------------------------------------------------ persistence


def _budget(db: Session, user_id: uuid.UUID, month: date) -> Budget:
    b = db.scalar(select(Budget).where(Budget.user_id == user_id, Budget.month == month))
    if b is None:
        raise AppError("budget_not_found", "No budget for this month.", 404)
    return b


def _out(adj: BudgetAdjustment) -> dict:
    return {
        "id": adj.id,
        "proposed_by": adj.proposed_by,
        "status": adj.status,
        "changes": adj.changes,
        "reason": adj.reason,
        "created_at": adj.created_at,
        "decided_at": adj.decided_at,
    }


def create_suggestion(db: Session, user_id: uuid.UUID) -> tuple[dict | None, str | None]:
    """Build (or return the open) suggestion for the current month.

    Returns (suggestion, message): a proposal to approve/reject, or just a message when
    nothing needs changing or no other category has room.
    """
    f = fc.month_forecast(db, user_id)
    month = date.fromisoformat(f["month"] + "-01")
    budget = _budget(db, user_id, month)
    open_one = db.scalar(
        select(BudgetAdjustment).where(
            BudgetAdjustment.budget_id == budget.id, BudgetAdjustment.status == "proposed"
        )
    )
    if open_one is not None:
        return _out(open_one), None
    s = suggest(
        [
            ItemOutlook(
                c["category"]["id"],
                c["category"]["name"],
                c["budget"],
                c["projected"],
                c["category"]["is_essential"],
            )
            for c in f["categories"]
        ]
    )
    if s is None:
        return None, "Every category is on track — no changes needed."
    if not s.changes:
        # Overshoot that no other category can absorb: inform, don't propose.
        return None, s.reason
    adj = BudgetAdjustment(
        budget_id=budget.id, proposed_by="system", changes=s.changes, reason=s.reason
    )
    db.add(adj)
    db.commit()
    return _out(adj), None


def _owned_adjustment(db: Session, user_id: uuid.UUID, adj_id: uuid.UUID) -> tuple:
    row = db.execute(
        select(BudgetAdjustment, Budget)
        .join(Budget, Budget.id == BudgetAdjustment.budget_id)
        .where(BudgetAdjustment.id == adj_id, Budget.user_id == user_id)
    ).first()
    if row is None:
        raise AppError("adjustment_not_found", "Suggestion not found.", 404)
    return row


def decide(db: Session, user_id: uuid.UUID, adj_id: uuid.UUID, approve: bool) -> dict:
    adj, budget = _owned_adjustment(db, user_id, adj_id)
    if adj.status != "proposed":
        raise AppError("adjustment_closed", f"This suggestion was already {adj.status}.", 409)
    if approve:
        items = {
            i.category_id: i
            for i in db.scalars(select(BudgetItem).where(BudgetItem.budget_id == budget.id))
        }
        # Refuse if the budget changed after the suggestion was made (stale numbers).
        for change in adj.changes:
            item = items.get(uuid.UUID(change["category_id"]))
            if item is None or f"{item.amount:.2f}" != change["old"]:
                raise AppError(
                    "budget_changed",
                    "Your budget changed after this suggestion was made. Ask for a new one.",
                    409,
                )
        for change in adj.changes:
            items[uuid.UUID(change["category_id"])].amount = Decimal(change["new"])
    adj.status = "approved" if approve else "rejected"
    adj.decided_at = datetime.now(UTC)
    db.commit()
    return _out(adj)


def history(db: Session, user_id: uuid.UUID, month: date) -> list[dict]:
    budget = db.scalar(select(Budget).where(Budget.user_id == user_id, Budget.month == month))
    if budget is None:
        return []
    rows = db.scalars(
        select(BudgetAdjustment)
        .where(BudgetAdjustment.budget_id == budget.id)
        .order_by(BudgetAdjustment.created_at.desc())
    )
    return [_out(a) for a in rows]


def record_manual_edit(
    db: Session,
    budget: Budget,
    old: dict[uuid.UUID, Decimal],
    new: dict[uuid.UUID, Decimal],
) -> None:
    """Called by save_budget: keep a history entry for the user's own changes."""
    ids = set(old) | set(new)
    if not ids or old == new:
        return
    names = dict(db.execute(select(Category.id, Category.name).where(Category.id.in_(ids))).all())
    changes = [
        {
            "category_id": str(cid),
            "category_name": names.get(cid, "?"),
            "old": f"{old.get(cid, ZERO):.2f}",
            "new": f"{new.get(cid, ZERO):.2f}",
        }
        for cid in ids
        if old.get(cid, ZERO) != new.get(cid, ZERO)
    ]
    if changes:
        db.add(
            BudgetAdjustment(
                budget_id=budget.id,
                proposed_by="user",
                changes=sorted(changes, key=lambda c: c["category_name"]),
                reason="Edited in the budget editor.",
                status="approved",
                decided_at=datetime.now(UTC),
            )
        )
