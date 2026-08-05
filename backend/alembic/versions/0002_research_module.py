"""Research module: expand research_runs, add report_metadata and report_files

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05 00:00:01.000000 UTC
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. Drop old research_runs (depends on old runstatus enum) ─────────────
    op.drop_table("research_runs")
    op.execute("DROP TYPE IF EXISTS runstatus CASCADE")

    # ── 2. Create new runstatus enum (9 values) ────────────────────────────────
    op.execute(
        "CREATE TYPE runstatus AS ENUM ("
        "'PENDING','QUEUED','SEARCHING','FILTERING',"
        "'EXTRACTING','GENERATING','COMPLETED','FAILED','CANCELLED')"
    )

    # ── 3. Create new research_runs table ─────────────────────────────────────
    op.create_table(
        "research_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Core
        sa.Column("compound_name", sa.String(255), nullable=False),
        # JSON fields
        sa.Column("competitors", postgresql.JSON, nullable=False, server_default="[]"),
        sa.Column("mentioned_websites", postgresql.JSON, nullable=False, server_default="[]"),
        sa.Column("publication_filter", postgresql.JSON, nullable=True),
        sa.Column("selected_sources", postgresql.JSON, nullable=False, server_default="[]"),
        # Status & versioning
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "QUEUED", "SEARCHING", "FILTERING",
                "EXTRACTING", "GENERATING", "COMPLETED", "FAILED", "CANCELLED",
                name="runstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("cache_key", sa.String(64), nullable=True),
        sa.Column("report_version", sa.Integer, nullable=False, server_default="1"),
        # Ownership
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        # Timestamps
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
        # Soft delete
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_runs_id", "research_runs", ["id"])
    op.create_index("ix_research_runs_compound_name", "research_runs", ["compound_name"])
    op.create_index("ix_research_runs_status", "research_runs", ["status"])
    op.create_index("ix_research_runs_created_by", "research_runs", ["created_by"])
    op.create_index("ix_research_runs_cache_key", "research_runs", ["cache_key"])
    op.create_index("ix_research_runs_deleted_at", "research_runs", ["deleted_at"])

    # ── 4. Create report_metadata table ───────────────────────────────────────
    op.create_table(
        "report_metadata",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("patent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
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
            ["research_run_id"], ["research_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_metadata_id", "report_metadata", ["id"])
    op.create_index(
        "ix_report_metadata_research_run_id", "report_metadata", ["research_run_id"]
    )

    # ── 5. Create reportfiletype enum ─────────────────────────────────────────
    op.execute("DROP TYPE IF EXISTS reportfiletype CASCADE")
    op.execute(
        "CREATE TYPE reportfiletype AS ENUM ('PDF','JSON','HTML','MARKDOWN','CSV')"
    )

    # ── 6. Create report_files table ──────────────────────────────────────────
    op.create_table(
        "report_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("report_metadata_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "file_type",
            postgresql.ENUM("PDF", "JSON", "HTML", "MARKDOWN", "CSV", name="reportfiletype", create_type=False),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
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
            ["report_metadata_id"], ["report_metadata.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_files_id", "report_files", ["id"])
    op.create_index(
        "ix_report_files_report_metadata_id", "report_files", ["report_metadata_id"]
    )


def downgrade() -> None:
    op.drop_table("report_files")
    op.execute("DROP TYPE IF EXISTS reportfiletype CASCADE")
    op.drop_table("report_metadata")
    op.drop_table("research_runs")
    op.execute("DROP TYPE IF EXISTS runstatus CASCADE")
    
    op.execute(
        "CREATE TYPE runstatus AS ENUM ('PENDING','RUNNING','COMPLETED','FAILED')"
    )
    op.create_table(
        "research_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("compound_name", sa.String(255), nullable=False),
        sa.Column("status", postgresql.ENUM("PENDING", "RUNNING", "COMPLETED", "FAILED",
                                     name="runstatus", create_type=False), nullable=False, server_default="PENDING"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_runs_id", "research_runs", ["id"])
    op.create_index("ix_research_runs_created_by", "research_runs", ["created_by"])
