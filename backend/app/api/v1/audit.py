"""
app/api/v1/audit.py

Audit log endpoints - admin only.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.schemas.common import SuccessResponse
from app.utils.exceptions import ForbiddenError

router = APIRouter(prefix="/api/v1/audit-log", tags=["Audit Log"])


@router.get(
    "",
    response_model=SuccessResponse[AuditLogListResponse],
    summary="Get audit log entries (admin only)",
    description="Retrieve paginated audit log entries. Only accessible by ADMIN users.",
)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[AuditLogListResponse]:
    # Admin-only access
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError(message="Only ADMIN users can access audit logs")

    # Build simple query
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    
    # Get total count
    from sqlalchemy import func
    count_query = select(func.count(AuditLog.id))
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    audit_logs = result.scalars().all()

    # Convert to response models (UUIDs will be auto-converted by field_validator)
    items = [AuditLogResponse.model_validate(log) for log in audit_logs]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return SuccessResponse(
        data=AuditLogListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )
