"""
app/models/report_metadata.py

ReportMetadata stores the high-level summary produced after a ResearchRun
reaches COMPLETED status. A single ResearchRun can have multiple metadata
records across different report_version values (when refresh_run() is called).
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.report_file import ReportFile
    from app.models.research_run import ResearchRun


class ReportMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    High-level metadata for a completed research report.
    Phase 2 will populate title, summary, patent_count, source_count, etc.
    """

    __tablename__ = "report_metadata"

    # ── Foreign key ───────────────────────────────────────────────────────────
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Report content metadata ───────────────────────────────────────────────
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    patent_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    research_run: Mapped["ResearchRun"] = relationship(
        "ResearchRun", back_populates="reports"
    )
    files: Mapped[list["ReportFile"]] = relationship(
        "ReportFile",
        back_populates="report_metadata",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<ReportMetadata id={self.id} "
            f"run={self.research_run_id} v{self.version}>"
        )
