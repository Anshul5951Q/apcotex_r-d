"""
app/db/database.py

Async SQLAlchemy engine and declarative Base.
All ORM models inherit from Base defined here.
"""
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# ── Async engine ──────────────────────────────────────────────────────────────
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # log SQL only in DEBUG mode
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,           # recycle stale connections
    pool_recycle=3600,            # recycle connections every 1 h
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """
    All ORM models must inherit from this class.
    Import this Base in Alembic's env.py so migrations detect model changes.
    """
    pass
