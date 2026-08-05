"""
app/api/v1/health.py

Health check endpoint.
Returns service status and a live database connectivity probe.
No authentication required — used by load balancers and monitoring.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import SuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=SuccessResponse[dict],
    summary="Service health check",
    description="Returns service status and database connectivity. No auth required.",
)
async def health_check(session: AsyncSession = Depends(get_db)) -> SuccessResponse[dict]:
    """Probe the database with a lightweight query and return overall health."""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        db_status = "unhealthy"

    return SuccessResponse(
        data={
            "status": "ok",
            "database": db_status,
            "service": "Apcotex R&D API",
        }
    )
