"""add_llm_provider_exhausted_to_runstatus

Revision ID: 4cdfa17814ca
Revises: f94d9022a692
Create Date: 2026-08-13 16:25:51.045841+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic
revision: str = '4cdfa17814ca'
down_revision: str | None = 'f94d9022a692'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add LLM_PROVIDER_EXHAUSTED to the runstatus enum type if it does not exist
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'LLM_PROVIDER_EXHAUSTED'")


def downgrade() -> None:
    # Postgres enum values cannot be easily removed without recreating the entire type.
    # We will safely ignore downgrade for this specific value addition.
    pass
