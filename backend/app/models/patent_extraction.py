import uuid
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin

class PatentExtraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "patent_extractions"

    research_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    patent_number: Mapped[str] = mapped_column(String, index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    assignee: Mapped[str] = mapped_column(String, nullable=True)
    publication_year: Mapped[str] = mapped_column(String, nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=True)
    
    # Optional URL back to Google Patents
    url: Mapped[str] = mapped_column(String, nullable=True)

    # Relationships
    parameters = relationship("ExtractedParameter", back_populates="extraction", cascade="all, delete-orphan")
