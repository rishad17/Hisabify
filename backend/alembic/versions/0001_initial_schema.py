"""Initial schema: profiles, wallets, categories, transactions, budgets, commitments, AI log.

Revision ID: 0001
Revises:
Create Date: 2026-11-10

Generated from the SQLAlchemy models (app/models). CI runs `alembic check` to make sure
models and migrations never drift apart.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=60), nullable=True),
        sa.Column(
            "preferred_language",
            sa.String(length=2),
            server_default=sa.text("'en'"),
            nullable=False,
        ),
        sa.Column(
            "timezone", sa.String(length=40), server_default=sa.text("'Asia/Dhaka'"), nullable=False
        ),
        sa.Column("store_ai_text", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("preferred_language IN ('en', 'bn')", name=op.f("ck_profiles_language")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profiles")),
    )
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("intent", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'clarify', 'error')", name=op.f("ck_ai_interactions_status")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_ai_interactions_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_interactions")),
    )
    op.create_index(
        "ix_ai_interactions_user_created",
        "ai_interactions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interactions_user_id"), "ai_interactions", ["user_id"], unique=False
    )
    op.create_table(
        "budgets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column(
            "planned_income",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "savings_target",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=10), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('draft', 'active')", name=op.f("ck_budgets_status")),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM month) = 1", name=op.f("ck_budgets_month_is_first_day")
        ),
        sa.CheckConstraint(
            "planned_income >= 0 AND savings_target >= 0", name=op.f("ck_budgets_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_budgets_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budgets")),
        sa.UniqueConstraint("user_id", "month", name=op.f("uq_budgets_user_id_month")),
    )
    op.create_index(op.f("ix_budgets_user_id"), "budgets", ["user_id"], unique=False)
    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("name_bn", sa.String(length=50), nullable=True),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("is_essential", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('expense', 'income')", name=op.f("ck_categories_kind")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_categories_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint(
            "user_id", "kind", "name", name=op.f("uq_categories_user_id_kind_name")
        ),
    )
    op.create_index(op.f("ix_categories_user_id"), "categories", ["user_id"], unique=False)
    op.create_table(
        "wallets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column(
            "opening_balance",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('cash', 'bkash', 'nagad', 'rocket', 'bank', 'savings', 'other')",
            name=op.f("ck_wallets_type"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_wallets_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallets")),
        sa.UniqueConstraint("user_id", "name", name=op.f("uq_wallets_user_id_name")),
    )
    op.create_index(op.f("ix_wallets_user_id"), "wallets", ["user_id"], unique=False)
    op.create_index(
        "uq_wallets_one_default_per_user",
        "wallets",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_table(
        "budget_adjustments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("proposed_by", sa.String(length=4), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=10), server_default=sa.text("'proposed'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "proposed_by IN ('ai', 'user')", name=op.f("ck_budget_adjustments_proposed_by")
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')",
            name=op.f("ck_budget_adjustments_status"),
        ),
        sa.ForeignKeyConstraint(
            ["budget_id"],
            ["budgets.id"],
            name=op.f("fk_budget_adjustments_budget_id_budgets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_adjustments")),
    )
    op.create_index(
        op.f("ix_budget_adjustments_budget_id"), "budget_adjustments", ["budget_id"], unique=False
    )
    op.create_table(
        "budget_items",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_budget_items_amount_non_negative")),
        sa.ForeignKeyConstraint(
            ["budget_id"],
            ["budgets.id"],
            name=op.f("fk_budget_items_budget_id_budgets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_budget_items_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_items")),
        sa.UniqueConstraint(
            "budget_id", "category_id", name=op.f("uq_budget_items_budget_id_category_id")
        ),
    )
    op.create_index(op.f("ix_budget_items_budget_id"), "budget_items", ["budget_id"], unique=False)
    op.create_table(
        "recurring_bills",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=True),
        sa.Column("due_day", sa.SmallInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_recurring_bills_amount_positive")),
        sa.CheckConstraint(
            "due_day BETWEEN 1 AND 31", name=op.f("ck_recurring_bills_due_day_range")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_recurring_bills_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_recurring_bills_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name=op.f("fk_recurring_bills_wallet_id_wallets"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_bills")),
    )
    op.create_index(
        op.f("ix_recurring_bills_user_id"), "recurring_bills", ["user_id"], unique=False
    )
    op.create_table(
        "savings_goals",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("wallet_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("target_amount > 0", name=op.f("ck_savings_goals_target_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_savings_goals_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name=op.f("fk_savings_goals_wallet_id_wallets"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_goals")),
    )
    op.create_index(op.f("ix_savings_goals_user_id"), "savings_goals", ["user_id"], unique=False)
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=12), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column("to_wallet_id", sa.UUID(), nullable=True),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("recurring_bill_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column(
            "source", sa.String(length=10), server_default=sa.text("'manual'"), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("batch_index", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(type = 'adjustment' AND amount <> 0) OR (type <> 'adjustment' AND amount > 0)",
            name=op.f("ck_transactions_amount_sign"),
        ),
        sa.CheckConstraint(
            "(type = 'transfer') = (to_wallet_id IS NOT NULL)",
            name=op.f("ck_transactions_transfer_has_target"),
        ),
        sa.CheckConstraint(
            "(type IN ('expense', 'income')) = (category_id IS NOT NULL)",
            name=op.f("ck_transactions_category_matches_type"),
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'text', 'voice')", name=op.f("ck_transactions_source")
        ),
        sa.CheckConstraint(
            "type IN ('expense', 'income', 'transfer', 'adjustment')",
            name=op.f("ck_transactions_type"),
        ),
        sa.CheckConstraint(
            "to_wallet_id IS NULL OR to_wallet_id <> wallet_id",
            name=op.f("ck_transactions_transfer_distinct_wallets"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_transactions_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recurring_bill_id"],
            ["recurring_bills.id"],
            name=op.f("fk_transactions_recurring_bill_id_recurring_bills"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_wallet_id"],
            ["wallets.id"],
            name=op.f("fk_transactions_to_wallet_id_wallets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_transactions_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name=op.f("fk_transactions_wallet_id_wallets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            "batch_index",
            name=op.f("uq_transactions_user_id_idempotency_key_batch_index"),
        ),
    )
    op.create_index(
        "ix_transactions_to_wallet",
        "transactions",
        ["to_wallet_id"],
        unique=False,
        postgresql_where=sa.text("to_wallet_id IS NOT NULL"),
    )
    op.create_index(
        "ix_transactions_user_category_date",
        "transactions",
        ["user_id", "category_id", "occurred_on"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_user_date_active",
        "transactions",
        ["user_id", sa.literal_column("occurred_on DESC")],
        unique=False,
        postgresql_where=sa.text("voided_at IS NULL"),
    )
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"], unique=False)
    op.create_index(op.f("ix_transactions_wallet_id"), "transactions", ["wallet_id"], unique=False)
    op.create_table(
        "expected_incomes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("expected_on", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=10), server_default=sa.text("'expected'"), nullable=False
        ),
        sa.Column("received_transaction_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('expected', 'received', 'cancelled')",
            name=op.f("ck_expected_incomes_status"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_expected_incomes_amount_positive")),
        sa.ForeignKeyConstraint(
            ["received_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_expected_incomes_received_transaction_id_transactions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["profiles.id"],
            name=op.f("fk_expected_incomes_user_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expected_incomes")),
    )
    op.create_index(
        op.f("ix_expected_incomes_user_id"), "expected_incomes", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_expected_incomes_user_id"), table_name="expected_incomes")
    op.drop_table("expected_incomes")
    op.drop_index(
        "ix_transactions_to_wallet",
        table_name="transactions",
        postgresql_where=sa.text("to_wallet_id IS NOT NULL"),
    )
    op.drop_index("ix_transactions_user_category_date", table_name="transactions")
    op.drop_index(
        "ix_transactions_user_date_active",
        table_name="transactions",
        postgresql_where=sa.text("voided_at IS NULL"),
    )
    op.drop_index(op.f("ix_transactions_user_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_wallet_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_savings_goals_user_id"), table_name="savings_goals")
    op.drop_table("savings_goals")
    op.drop_index(op.f("ix_recurring_bills_user_id"), table_name="recurring_bills")
    op.drop_table("recurring_bills")
    op.drop_index(op.f("ix_budget_items_budget_id"), table_name="budget_items")
    op.drop_table("budget_items")
    op.drop_index(op.f("ix_budget_adjustments_budget_id"), table_name="budget_adjustments")
    op.drop_table("budget_adjustments")
    op.drop_index(op.f("ix_wallets_user_id"), table_name="wallets")
    op.drop_index(
        "uq_wallets_one_default_per_user",
        table_name="wallets",
        postgresql_where=sa.text("is_default"),
    )
    op.drop_table("wallets")
    op.drop_index(op.f("ix_categories_user_id"), table_name="categories")
    op.drop_table("categories")
    op.drop_index(op.f("ix_budgets_user_id"), table_name="budgets")
    op.drop_table("budgets")
    op.drop_index("ix_ai_interactions_user_created", table_name="ai_interactions")
    op.drop_index(op.f("ix_ai_interactions_user_id"), table_name="ai_interactions")
    op.drop_table("ai_interactions")
    op.drop_table("profiles")
