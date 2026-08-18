"""
app/models/optimized_recipe_candidate.py

OptimizedRecipeCandidate — one of the 3 LLM-generated optimizations based on trial feedback.
"""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.customer_trial import CustomerTrial


class OptimizedRecipeCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One LLM-generated optimized recipe. Exactly 3 exist per CustomerTrial (generated once).
    Includes a list of changes from the base recipe and predicted impacts.
    """
    __tablename__ = "optimized_recipe_candidates"

    trial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_trials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    revision_label: Mapped[str] = mapped_column(String(16), nullable=False)  # "A", "B", "C"
    name: Mapped[str] = mapped_column(String(128), nullable=False)           # "Recipe X – Revision A"

    # Full structured recipe from LLM
    recipe_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # What changed from the original recipe
    # [{"parameter": "CTA", "previous": "0.45", "revised": "0.60", "rationale": "..."}]
    changed_parameters: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")

    # What the model expects the impact to be on the trial results
    # [{"property": "Mooney", "previous_value": "47", "predicted_value": "50"}]
    predicted_impacts: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")

    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # ── Relationships ─────────────────────────────────────────────────────────
    trial: Mapped["CustomerTrial"] = relationship("CustomerTrial", back_populates="optimized_candidates")

    def __repr__(self) -> str:
        return f"<OptimizedRecipeCandidate id={self.id} trial={self.trial_id} revision={self.revision_label}>"
