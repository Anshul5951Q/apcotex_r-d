"""
app/models/recipe_cycle.py

RecipeCycle — one recipe generation session linked to a patent research run.
A user can create multiple cycles from the same research run.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.research_run import ResearchRun
    from app.models.report_metadata import ReportMetadata
    from app.models.recipe_candidate import RecipeCandidate
    from app.models.customer_trial import CustomerTrial


class RecipeCycleStatus(str, Enum):
    PENDING = "PENDING"
    STEP1 = "STEP1"          # Target spec entered, not yet generated
    GENERATING = "GENERATING" # LLM generating recipes
    STEP2 = "STEP2"          # Recipes generated, user selecting
    STEP3 = "STEP3"          # Recipe selected, customer trial in progress
    OPTIMIZING = "OPTIMIZING" # LLM generating optimizations
    STEP4 = "STEP4"          # Optimizations ready, user selecting
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RecipeCycle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One recipe generation session. Linked to a patent research run.
    Carries the full history: target spec → candidates → trial → optimizations.
    """
    __tablename__ = "recipe_cycles"

    # ── Foreign keys ─────────────────────────────────────────────────────────
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_metadata_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_metadata.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Core fields ──────────────────────────────────────────────────────────
    compound_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[RecipeCycleStatus] = mapped_column(
        SAEnum(RecipeCycleStatus, name="recipecyclestatus", create_constraint=True),
        nullable=False,
        default=RecipeCycleStatus.PENDING,
        server_default=RecipeCycleStatus.PENDING.value,
        index=True,
    )

    # ── User-entered spec (Step 1) ────────────────────────────────────────────
    # [{id, feature, unit, min, max, category, dataType}]
    target_properties: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    # [{name: "Company A", values: {feature: value}}]
    competitor_data: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    # ── Compact patent context built at Step 1→Step2 ──────────────────────────
    # Structured synthesis evidence sent to LLM — NOT raw HTML
    patent_context_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Selection ────────────────────────────────────────────────────────────
    selected_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # ── Soft delete ──────────────────────────────────────────────────────────
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    research_run: Mapped["ResearchRun"] = relationship(
        "ResearchRun",
        back_populates="recipe_cycles",
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    candidates: Mapped[list["RecipeCandidate"]] = relationship(
        "RecipeCandidate",
        back_populates="cycle",
        cascade="all, delete-orphan",
        order_by="RecipeCandidate.rank",
    )
    trials: Mapped[list["CustomerTrial"]] = relationship(
        "CustomerTrial",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<RecipeCycle id={self.id} compound={self.compound_name!r} status={self.status}>"
