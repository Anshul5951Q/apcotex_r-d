import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Text, ForeignKey, Enum as SAEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum
from datetime import datetime

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.research_run import ResearchRun

class BatchStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ExtractionBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extraction_batches"

    research_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    patent_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list) # List of patent numbers
    
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    status: Mapped[BatchStatus] = mapped_column(
        SAEnum(BatchStatus, name="batchstatus", create_constraint=True),
        nullable=False,
        default=BatchStatus.PENDING
    )
    
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    run: Mapped["ResearchRun"] = relationship()
