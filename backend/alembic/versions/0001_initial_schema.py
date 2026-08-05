"""Initial schema: users and research_runs tables

Revision ID: 0001
Revises:
Create Date: 2026-08-05 00:00:00.000000 UTC
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── ENUM types ────────────────────────────────────────────────────────────
    op.execute("DROP TYPE IF EXISTS userrole CASCADE")
    op.execute("CREATE TYPE userrole AS ENUM ('ADMIN', 'SCIENTIST')")

    op.execute("DROP TYPE IF EXISTS runstatus CASCADE")
    op.execute("CREATE TYPE runstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')")

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("ADMIN", "SCIENTIST", name="userrole", create_type=False),
            nullable=False,
            server_default="SCIENTIST",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── research_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "research_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("compound_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("PENDING", "RUNNING", "COMPLETED", "FAILED", name="runstatus", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_runs_id", "research_runs", ["id"])
    op.create_index("ix_research_runs_created_by", "research_runs", ["created_by"])


def downgrade() -> None:
    op.drop_table("research_runs")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS runstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS userrole CASCADE")
