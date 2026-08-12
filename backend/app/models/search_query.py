import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.research_run import ResearchRun
    from app.models.search_result import SearchResult

class SearchQueryStatus(str, Enum):
    PENDING = "PENDING"
    SEARCHING = "SEARCHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class SearchQueryModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_queries"

    research_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    query_text: Mapped[str] = mapped_column(String(500), nullable=False)
    field: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. TITLE, TAC
    category: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. POLYMERIZATION
    jurisdiction: Mapped[str] = mapped_column(String(10), nullable=True)
    date_start: Mapped[str | None] = mapped_column(String(20), nullable=True) # e.g. 20210101
    date_end: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[SearchQueryStatus] = mapped_column(
        SAEnum(SearchQueryStatus, name="searchquerystatus", create_constraint=True),
        nullable=False,
        default=SearchQueryStatus.PENDING
    )
    
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    result_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    run: Mapped["ResearchRun"] = relationship()
    results: Mapped[list["SearchResult"]] = relationship(back_populates="search_query")
