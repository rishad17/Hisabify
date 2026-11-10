"""Orchestrates one AI message: load context → normalize → LLM → validate → draft.

    user text ──► normalize ──► Gemini (structured JSON) ──► build_draft (pure Python)
                                                              │
                                     duplicate check (DB) ◄───┘
                                                              │
                                    log usage (no raw text unless opted in)
                                                              ▼
                                                  draft for the user to confirm

Nothing is saved here. The confirmed draft goes through POST /transactions/batch.
"""

import logging
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.drafts import Draft, DraftItem, Issue, build_draft, flag_reused_amounts
from app.ai.extraction import CategoryInfo, WalletInfo, extract
from app.ai.llm_client import LLMClient, LLMError
from app.ai.normalize import normalize_user_text
from app.core.errors import AppError
from app.models import AIInteraction, Category, Profile, Transaction, Wallet
from app.services.ledger import today_for

logger = logging.getLogger(__name__)

UNSUPPORTED_MESSAGES = {
    "question": (
        "Questions about your spending are coming soon. For now, check the Dashboard and "
        "Transactions pages."
    ),
    "budget": "Budget planning is coming soon.",
}
OTHER_MESSAGE = (
    'I can record expenses, income and transfers. Try: "Ajke 50 taka cha" or '
    '"Cash theke bKash e 1000 taka".'
)


def _load_context(db: Session, user_id: uuid.UUID):
    categories = [
        CategoryInfo(c.id, c.name, c.name_bn, c.kind, c.icon)
        for c in db.scalars(
            select(Category).where(Category.user_id == user_id, Category.archived_at.is_(None))
        )
    ]
    wallets = [
        WalletInfo(w.id, w.name, w.type, w.is_default)
        for w in db.scalars(
            select(Wallet).where(Wallet.user_id == user_id, Wallet.archived_at.is_(None))
        )
    ]
    profile = db.get(Profile, user_id)
    return categories, wallets, profile


def _flag_possible_duplicates(
    db: Session, user_id: uuid.UUID, items: list[DraftItem], tz: str
) -> None:
    """Warn (never block) when a very similar transaction already exists on that day."""
    for item in items:
        stmt = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.voided_at.is_(None),
            Transaction.type == item.type,
            Transaction.amount == item.amount,
            Transaction.occurred_on == item.occurred_on,
        )
        if item.category is not None:
            stmt = stmt.where(Transaction.category_id == item.category.id)
        existing = db.scalars(stmt.order_by(Transaction.created_at.desc()).limit(1)).first()
        if existing is not None:
            local = existing.created_at.astimezone(ZoneInfo(tz))
            label = existing.description or "a transaction"
            item.issues.append(
                Issue(
                    "possible_duplicate",
                    f'Looks like "{label}" for the same amount saved at {local:%I:%M %p}. '
                    "Remove this one if it's a repeat.",
                )
            )


def _log(
    db: Session,
    *,
    user_id: uuid.UUID,
    intent: str | None,
    status: str,
    model: str | None = None,
    latency_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    text: str | None = None,
) -> None:
    db.add(
        AIInteraction(
            user_id=user_id,
            intent=intent,
            status=status,
            model=model,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            input_text=text,
        )
    )
    db.commit()


def process_message(
    db: Session, user_id: uuid.UUID, text: str, *, llm: LLMClient, source: str = "text"
) -> dict:
    categories, wallets, profile = _load_context(db, user_id)
    store_text = bool(profile and profile.store_ai_text)
    language = profile.preferred_language if profile else "en"
    today = today_for(db, user_id)
    clean = normalize_user_text(text)

    if not clean:
        raise AppError("empty_message", "Type what you spent or received.", 422)

    try:
        result = extract(
            llm, text=clean, today=today, categories=categories, wallets=wallets, language=language
        )
    except LLMError as exc:
        logger.warning("AI extraction failed: %s", exc)
        _log(db, user_id=user_id, intent=None, status="error", text=clean if store_text else None)
        raise AppError(
            "ai_unavailable",
            "The AI is busy right now. Try again in a moment, or add it manually.",
            status_code=503,
        ) from exc

    draft: Draft = build_draft(result.data, categories=categories, wallets=wallets, today=today)
    flag_reused_amounts(draft.items, clean)
    _flag_possible_duplicates(
        db, user_id, draft.items, profile.timezone if profile else "Asia/Dhaka"
    )

    response = _to_response(draft, source)
    _log(
        db,
        user_id=user_id,
        intent=draft.intent,
        status="clarify" if response["kind"] == "clarification" else "ok",
        model=result.model,
        latency_ms=result.latency_ms,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        text=clean if store_text else None,
    )
    return response


def _to_response(draft: Draft, source: str) -> dict:
    if draft.items or draft.planned:
        return {
            "kind": "transaction_draft",
            "clarifications": draft.clarifications,
            "message": (
                "Planned items aren't recorded until they happen." if draft.planned else None
            ),
            "draft": {
                "draft_id": uuid.uuid4().hex,
                "source": source,
                "items": [_item_out(i) for i in draft.items],
                "planned": [
                    {"description": p.description, "amount": p.amount, "date": p.date}
                    for p in draft.planned
                ],
                "expense_total": draft.expense_total,
                "income_total": draft.income_total,
            },
        }
    if draft.intent in UNSUPPORTED_MESSAGES:
        return {"kind": "unsupported", "message": UNSUPPORTED_MESSAGES[draft.intent]}
    if draft.clarifications:
        return {
            "kind": "clarification",
            "message": draft.clarifications[0],
            "clarifications": draft.clarifications,
        }
    return {"kind": "unsupported", "message": OTHER_MESSAGE}


def _item_out(item: DraftItem) -> dict:
    cat = item.category
    return {
        "type": item.type,
        "amount": item.amount,
        "description": item.description,
        "category": (
            {"id": cat.id, "name": cat.name, "name_bn": cat.name_bn, "icon": cat.icon}
            if cat
            else None
        ),
        "wallet_id": item.wallet.id if item.wallet else None,
        "wallet_name": item.wallet.name if item.wallet else None,
        "to_wallet_id": item.to_wallet.id if item.to_wallet else None,
        "to_wallet_name": item.to_wallet.name if item.to_wallet else None,
        "occurred_on": item.occurred_on,
        "wallet_defaulted": item.wallet_defaulted,
        "issues": [
            {"code": i.code, "message": i.message, "severity": i.severity} for i in item.issues
        ],
    }
