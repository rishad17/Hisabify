"""Validate raw LLM output and turn it into a transaction DRAFT the user can confirm.

Everything here is deterministic Python — no AI, no database — so it's easy to test.
The LLM output is untrusted: amounts are re-parsed as Decimal, categories and wallets
must match the user's real ones, dates are checked, and anything doubtful becomes an
`issue` shown in the preview instead of being silently "fixed".

Nothing in this module saves anything. Saving happens only after the user confirms,
through the normal /transactions/batch endpoint, which validates everything again.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from app.ai.extraction import CategoryInfo, WalletInfo

MAX_AMOUNT = Decimal("999999999999.99")
OLD_DATE_DAYS = 365
FALLBACK_CATEGORY = {"expense": "Miscellaneous", "income": "Other Income"}

Severity = Literal["warning", "error"]


@dataclass
class Issue:
    code: str
    message: str
    severity: Severity = "warning"  # "error" = must be fixed in the preview before saving


@dataclass
class DraftItem:
    type: str
    amount: Decimal
    description: str
    occurred_on: date
    wallet: WalletInfo | None
    to_wallet: WalletInfo | None = None
    category: CategoryInfo | None = None
    wallet_defaulted: bool = False
    issues: list[Issue] = field(default_factory=list)


@dataclass
class PlannedItem:
    description: str
    amount: Decimal | None
    date: date | None


@dataclass
class Draft:
    intent: str
    items: list[DraftItem]
    planned: list[PlannedItem]
    clarifications: list[str]

    @property
    def expense_total(self) -> Decimal:
        return sum((i.amount for i in self.items if i.type == "expense"), Decimal("0.00"))

    @property
    def income_total(self) -> Decimal:
        return sum((i.amount for i in self.items if i.type == "income"), Decimal("0.00"))


# ------------------------------------------------------------------- parsing helpers


def parse_amount(raw: Any) -> Decimal | None:
    """'1,500' / '1500.5' / 1500 → Decimal('1500.50'); anything else → None."""
    if isinstance(raw, bool) or raw is None:
        return None
    text = str(raw).strip().replace(",", "").replace("৳", "")
    text = re.sub(r"(?i)\s*(tk|taka|টাকা)$", "", text).strip()
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        return None
    try:
        value = Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    if value <= 0 or value > MAX_AMOUNT:
        return None
    return value


def parse_date(raw: Any) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def _match_category(
    name: Any, kind: str, categories: list[CategoryInfo]
) -> tuple[CategoryInfo | None, bool]:
    """Returns (category, exact). Falls back to Miscellaneous / Other Income."""
    pool = [c for c in categories if c.kind == kind]
    if isinstance(name, str) and name.strip():
        key = name.strip().casefold()
        for c in pool:
            if c.name.casefold() == key or (c.name_bn and c.name_bn.casefold() == key):
                return c, True
    fallback = next((c for c in pool if c.name == FALLBACK_CATEGORY[kind]), None)
    return fallback or (pool[0] if pool else None), False


def _match_wallet(name: Any, wallets: list[WalletInfo]) -> WalletInfo | None:
    if not isinstance(name, str) or not name.strip():
        return None
    key = name.strip().casefold()
    for w in wallets:
        if w.name.casefold() == key:
            return w
    # "bkash" → the user's only wallet of type bkash, even if they named it "Personal bKash"
    by_type = [w for w in wallets if w.type == key]
    return by_type[0] if len(by_type) == 1 else None


# ------------------------------------------------------------------- main entry


def build_draft(
    raw: dict[str, Any],
    *,
    categories: list[CategoryInfo],
    wallets: list[WalletInfo],
    today: date,
) -> Draft:
    intent = raw.get("intent") if raw.get("intent") in ("record", "question", "budget") else "other"
    clarifications: list[str] = []
    if isinstance(raw.get("clarification"), str) and raw["clarification"].strip():
        clarifications.append(raw["clarification"].strip()[:300])

    default_wallet = next((w for w in wallets if w.is_default), wallets[0] if wallets else None)
    items: list[DraftItem] = []
    planned: list[PlannedItem] = []

    raw_items = raw.get("transactions") if isinstance(raw.get("transactions"), list) else []
    for raw_item in raw_items[:20]:
        if not isinstance(raw_item, dict):
            continue
        tx_type = raw_item.get("type")
        if tx_type not in ("expense", "income", "transfer"):
            continue
        description = str(raw_item.get("description") or "").strip()[:200]
        amount = parse_amount(raw_item.get("amount"))
        occurred_on = parse_date(raw_item.get("date"))

        # Future plans are listed but never recorded.
        if raw_item.get("is_planned") is True or (occurred_on and occurred_on > today):
            planned.append(PlannedItem(description or "Planned item", amount, occurred_on))
            continue

        if amount is None:
            label = f'"{description}"' if description else "one item"
            clarifications.append(f"How much was {label}? I couldn't read the amount.")
            continue

        item = DraftItem(
            type=tx_type,
            amount=amount,
            description=description,
            occurred_on=occurred_on or today,
            wallet=None,
        )

        if occurred_on and (today - occurred_on) > timedelta(days=OLD_DATE_DAYS):
            item.issues.append(
                Issue("date_old", "This date is more than a year ago — is it right?")
            )

        # Wallets
        named_wallet = _match_wallet(raw_item.get("wallet"), wallets)
        if named_wallet is None and raw_item.get("wallet"):
            item.issues.append(
                Issue("wallet_unknown", f'No wallet named "{raw_item["wallet"]}" — using default.')
            )
        item.wallet = named_wallet or default_wallet
        item.wallet_defaulted = named_wallet is None
        if item.wallet is None:
            item.issues.append(Issue("wallet_missing", "Choose a wallet.", "error"))

        if tx_type == "transfer":
            item.to_wallet = _match_wallet(raw_item.get("to_wallet"), wallets)
            if item.to_wallet is None:
                item.issues.append(
                    Issue("transfer_needs_target", "Choose the wallet the money went to.", "error")
                )
            elif item.wallet and item.to_wallet.id == item.wallet.id:
                item.issues.append(
                    Issue("transfer_same_wallet", "From and to wallets must differ.", "error")
                )
        else:
            category, exact = _match_category(raw_item.get("category"), tx_type, categories)
            item.category = category
            if category is None:
                item.issues.append(Issue("category_missing", "Choose a category.", "error"))
            elif not exact:
                item.issues.append(
                    Issue(
                        "category_guessed",
                        f'Not sure about the category — set to "{category.name}".',
                    )
                )

        if not item.description:
            item.description = (
                item.category.name if item.category else "Transfer" if tx_type == "transfer" else ""
            )
        items.append(item)

    if intent == "record" and not items and not planned and not clarifications:
        clarifications.append("I couldn't find an amount to record. How much, and for what?")

    return Draft(intent=intent, items=items, planned=planned, clarifications=clarifications)
