"""Enable Row Level Security on every table (with NO policies).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10

Why: Supabase automatically exposes the `public` schema through its REST API
(PostgREST) to anyone holding the public anon/publishable key. Our frontend never uses
that API — all data goes through FastAPI — so we lock it shut:

  * RLS enabled + zero policies  →  the `anon` and `authenticated` roles see nothing.
  * Our backend connects as the table owner (`postgres`), which bypasses RLS, and
    enforces per-user access itself by filtering every query on the verified user id.

Defense in depth: even if someone finds the anon key, they cannot read financial data.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "profiles",
    "wallets",
    "categories",
    "transactions",
    "budgets",
    "budget_items",
    "budget_adjustments",
    "recurring_bills",
    "expected_incomes",
    "savings_goals",
    "ai_interactions",
    "alembic_version",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
