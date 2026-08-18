import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.research_run import ResearchRun
    from app.models.search_query import SearchQueryModel

class TitleScreeningStatus(str, Enum):
    PENDING = "PENDING"
    STRONG = "STRONG"
    MEDIUM = "MEDIUM"
    WEAK = "WEAK"
    REJECT = "REJECT"

class SearchResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_results"

    research_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    search_query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publication_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    publication_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    title_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    title_screening_status: Mapped[TitleScreeningStatus] = mapped_column(
        SAEnum(TitleScreeningStatus, name="titlescreeningstatus", create_constraint=True),
        nullable=False,
        default=TitleScreeningStatus.PENDING,
        index=True
    )
    
    discovered_by_queries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    # Discovery provenance
    discovery_source: Mapped[str | None] = mapped_column(String(20), nullable=True, default="NORMAL")
    competitor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    gemini_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gemini_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gemini_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    selection_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_final_selection: Mapped[bool] = mapped_column(nullable=True, default=False)

    # Relationships
    run: Mapped["ResearchRun"] = relationship()
    search_query: Mapped["SearchQueryModel"] = relationship(back_populates="results")
