"""
app/models/api_usage_log.py

ORM model for capturing all API and LLM usage telemetry.
"""
import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

class APIUsageLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_usage_logs"

    research_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=True)
    operation: Mapped[str] = mapped_column(String(100), nullable=True)
    
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    
    input_cost: Mapped[float] = mapped_column(Float, nullable=True)
    output_cost: Mapped[float] = mapped_column(Float, nullable=True)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=True)
    
    # "actual", "estimated", "unavailable", "configured_pricing"
    usage_source: Mapped[str] = mapped_column(String(50), nullable=True)
    
    request_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=True)
    
    error_type: Mapped[str] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(String(500), nullable=True)
    
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=True)

