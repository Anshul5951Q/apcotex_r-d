import uuid
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin

class ExtractedParameter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "extracted_parameters"

    patent_extraction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patent_extractions.id", ondelete="CASCADE"), index=True, nullable=False)
    
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=True)
    
    # Context provenance
    context: Mapped[str] = mapped_column(Text, nullable=True)
    section: Mapped[str] = mapped_column(String, nullable=True)
    confidence: Mapped[str] = mapped_column(String, nullable=True)
    example_number: Mapped[str] = mapped_column(String, nullable=True)
    source_sentence: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    extraction = relationship("PatentExtraction", back_populates="parameters")
