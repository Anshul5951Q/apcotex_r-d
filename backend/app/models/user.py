"""
app/models/user.py

User ORM model and UserRole enum.
"""
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.research_run import ResearchRun


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    SCIENTIST = "SCIENTIST"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Platform users.
    Roles: ADMIN (full access), SCIENTIST (standard researcher).
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole", create_constraint=True),
        nullable=False,
        default=UserRole.SCIENTIST,
        server_default=UserRole.SCIENTIST.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    research_runs: Mapped[list["ResearchRun"]] = relationship(
        "ResearchRun",
        back_populates="creator",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"
