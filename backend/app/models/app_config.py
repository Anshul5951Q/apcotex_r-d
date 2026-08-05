"""
app/models/app_config.py

Database model for application-wide settings.
"""
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class AppConfig(Base):
    """
    Stores global application configuration as key-value pairs.
    Value is stored as JSONB to allow complex configurations if needed.
    """
    __tablename__ = "app_configs"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return f"<AppConfig(key={self.key})>"
