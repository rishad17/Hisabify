"""Allow 'system' as a budget adjustment proposer.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11

Budget suggestions are produced by a deterministic engine, not an LLM, so labelling them
"ai" would be misleading. Manual budget edits are recorded too ("user").
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Full name already includes the naming-convention prefix → wrap in op.f() when dropping.
CK = "ck_budget_adjustments_proposed_by"


def upgrade() -> None:
    op.drop_constraint(op.f(CK), "budget_adjustments", type_="check")
    op.alter_column(
        "budget_adjustments",
        "proposed_by",
        type_=sa.String(length=10),
        existing_type=sa.String(length=4),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "proposed_by", "budget_adjustments", "proposed_by IN ('ai', 'system', 'user')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f(CK), "budget_adjustments", type_="check")
    op.execute("DELETE FROM budget_adjustments WHERE proposed_by = 'system'")
    op.alter_column(
        "budget_adjustments",
        "proposed_by",
        type_=sa.String(length=4),
        existing_type=sa.String(length=10),
        existing_nullable=False,
    )
    op.create_check_constraint("proposed_by", "budget_adjustments", "proposed_by IN ('ai', 'user')")
