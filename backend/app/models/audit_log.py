"""
app/models/audit_log.py

AuditLog ORM model for tracking business events.
"""
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Audit trail for business events.
    Records who did what, when, and with what details.
    """

    __tablename__ = "audit_log"

    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(
        String(36), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    detail: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} user_id={self.user_id} action={self.action} entity_type={self.entity_type}>"
