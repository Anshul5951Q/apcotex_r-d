"""Add COMPLETED_PARTIAL to runstatus enum

Revision ID: 6706b38e3bb1
Revises: 9c7e23e83fca
Create Date: 2026-08-10 12:33:10.353004+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic
revision: str = '6706b38e3bb1'
down_revision: str | None = '9c7e23e83fca'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add COMPLETED_PARTIAL to the runstatus enum if it does not already exist
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'COMPLETED_PARTIAL'")

def downgrade() -> None:
    # Postgres doesn't easily support dropping enum values without recreating the entire type
    # Since this is an additive change, we'll leave it as is for downgrade
    pass
