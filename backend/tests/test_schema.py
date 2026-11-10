"""Database schema guarantees (needs PostgreSQL)."""

import uuid
from decimal import Decimal

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.models import Category, Transaction, Wallet
from app.services.onboarding import ensure_profile
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.db


def test_models_and_migrations_match(db_engine):
    """Fails if someone changes a model without writing a migration."""
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.check(cfg)


def test_rls_enabled_on_every_table(db_session):
    rows = db_session.execute(
        text(
            "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"
        )
    ).all()
    assert rows == [], f"Tables without RLS: {rows}"


def test_money_is_exact_numeric(db_session):
    col_type = db_session.execute(
        text(
            "SELECT data_type, numeric_precision, numeric_scale FROM information_schema.columns "
            "WHERE table_name = 'transactions' AND column_name = 'amount'"
        )
    ).one()
    assert tuple(col_type) == ("numeric", 14, 2)


@pytest.fixture
def setup(db_session):
    user_id = uuid.uuid4()
    ensure_profile(db_session, user_id)
    cash = db_session.query(Wallet).filter_by(user_id=user_id, name="Cash").one()
    bkash = Wallet(user_id=user_id, name="bKash", type="bkash")
    db_session.add(bkash)
    db_session.flush()
    food = db_session.query(Category).filter_by(user_id=user_id, name="Food & Drinks").one()
    return user_id, cash, bkash, food


def _tx(user_id, wallet, **kw) -> Transaction:
    from datetime import date

    return Transaction(user_id=user_id, wallet_id=wallet.id, occurred_on=date(2026, 11, 10), **kw)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "expense", "amount": Decimal("0")},  # zero amount
        {"type": "expense", "amount": Decimal("-50")},  # negative expense
        {"type": "expense", "amount": Decimal("50")},  # expense without category
        {"type": "transfer", "amount": Decimal("50")},  # transfer without target wallet
        {"type": "bribe", "amount": Decimal("50")},  # unknown type
    ],
)
def test_database_rejects_invalid_transactions(db_session, setup, kwargs):
    user_id, cash, _, _ = setup
    db_session.add(_tx(user_id, cash, **kwargs))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_transfer_to_same_wallet_rejected(db_session, setup):
    user_id, cash, _, _ = setup
    db_session.add(_tx(user_id, cash, type="transfer", amount=Decimal("10"), to_wallet_id=cash.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_transfer_with_category_rejected(db_session, setup):
    user_id, cash, bkash, food = setup
    db_session.add(
        _tx(
            user_id,
            cash,
            type="transfer",
            amount=Decimal("10"),
            to_wallet_id=bkash.id,
            category_id=food.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_valid_rows_accepted_and_amount_stays_exact(db_session, setup):
    user_id, cash, bkash, food = setup
    expense = _tx(user_id, cash, type="expense", amount=Decimal("0.10"), category_id=food.id)
    transfer = _tx(user_id, cash, type="transfer", amount=Decimal("1000"), to_wallet_id=bkash.id)
    adjustment = _tx(user_id, cash, type="adjustment", amount=Decimal("-25.50"))
    db_session.add_all([expense, transfer, adjustment])
    db_session.flush()
    total = db_session.execute(
        text("SELECT SUM(amount) FROM transactions WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    assert total == Decimal("974.60")  # exact — no float rounding


def test_duplicate_idempotency_key_rejected(db_session, setup):
    user_id, cash, _, food = setup
    for _ in range(2):
        db_session.add(
            _tx(
                user_id,
                cash,
                type="expense",
                amount=Decimal("50"),
                category_id=food.id,
                idempotency_key="abc",
                batch_index=0,
            )
        )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_only_one_default_wallet(db_session, setup):
    user_id, *_ = setup
    db_session.add(Wallet(user_id=user_id, name="Second", type="cash", is_default=True))
    with pytest.raises(IntegrityError):
        db_session.flush()
