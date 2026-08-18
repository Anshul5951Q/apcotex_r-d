"""
app/schemas/audit.py

Schemas for audit log API.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AuditLogResponse(BaseModel):
    """Audit log entry response."""

    id: str
    user_id: str
    entity_type: str
    entity_id: Optional[str] = None
    action: str
    detail: dict
    created_at: datetime
    updated_at: datetime

    @field_validator('id', 'user_id', 'entity_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator('detail', mode='before')
    @classmethod
    def ensure_dict(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except:
                return {"raw": v}
        if v is None:
            return {}
        return dict(v)

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
