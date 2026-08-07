from sqlalchemy import Text, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin

class PatentDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "patent_documents"

    patent_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    abstract: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    examples: Mapped[str] = mapped_column(Text, nullable=True)
    experimental_section: Mapped[str] = mapped_column(Text, nullable=True)
    manufacturing_section: Mapped[str] = mapped_column(Text, nullable=True)
    polymerization_section: Mapped[str] = mapped_column(Text, nullable=True)
    claims: Mapped[str] = mapped_column(Text, nullable=True)
    cpc: Mapped[str] = mapped_column(Text, nullable=True)
    ipc: Mapped[str] = mapped_column(Text, nullable=True)
    publication_date: Mapped[str] = mapped_column(String, nullable=True)
