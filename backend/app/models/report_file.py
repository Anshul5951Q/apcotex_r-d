"""
app/models/report_file.py

ReportFile stores references to generated output files (PDF, JSON, HTML, etc.)
for a given ReportMetadata record. Phase 2 will populate file_path when the
report generation pipeline writes actual files or uploads to object storage.
"""
import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.report_metadata import ReportMetadata


class ReportFileType(str, Enum):
    PDF = "PDF"
    JSON = "JSON"
    HTML = "HTML"
    MARKDOWN = "MARKDOWN"
    CSV = "CSV"


class ReportFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single generated output file associated with a ReportMetadata.
    file_path may be a local filesystem path or an object-storage URL.
    """

    __tablename__ = "report_files"

    # ── Foreign key ───────────────────────────────────────────────────────────
    report_metadata_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_metadata.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── File descriptor ───────────────────────────────────────────────────────
    file_type: Mapped[ReportFileType] = mapped_column(
        SAEnum(ReportFileType, name="reportfiletype", create_constraint=True),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # ── Relationship ──────────────────────────────────────────────────────────
    report_metadata: Mapped["ReportMetadata"] = relationship(
        "ReportMetadata", back_populates="files"
    )

    def __repr__(self) -> str:
        return (
            f"<ReportFile id={self.id} type={self.file_type} "
            f"name={self.file_name!r}>"
        )
