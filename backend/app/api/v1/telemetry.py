from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.models.api_usage_log import APIUsageLog

router = APIRouter()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/{research_id}/usage")
async def get_run_usage(research_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return all raw API usage logs for a research run."""
    result = await db.execute(
        select(APIUsageLog)
        .where(APIUsageLog.research_run_id == research_id)
        .order_by(APIUsageLog.created_at.asc())
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "stage": log.stage,
            "provider": log.provider,
            "model": log.model,
            "operation": log.operation,
            "input_tokens": log.input_tokens,
            "output_tokens": log.output_tokens,
            "total_tokens": log.total_tokens,
            "estimated_cost": log.estimated_cost,
            "request_count": log.request_count,
            "latency_ms": log.latency_ms,
            "status": log.status,
            "http_status": log.http_status,
            "error_message": log.error_message,
            "retry_count": log.retry_count,
            "created_at": log.created_at,
            "metadata": log.metadata_json
        }
        for log in logs
    ]


@router.get("/{research_id}/usage/summary")
async def get_run_usage_summary(research_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return aggregated cost and token totals for a research run."""
    result = await db.execute(
        select(
            func.sum(APIUsageLog.estimated_cost).label("total_cost"),
            func.sum(APIUsageLog.total_tokens).label("total_tokens"),
            func.sum(APIUsageLog.request_count).label("total_requests"),
            func.sum(APIUsageLog.input_tokens).label("input_tokens"),
            func.sum(APIUsageLog.output_tokens).label("output_tokens")
        )
        .where(APIUsageLog.research_run_id == research_id)
    )
    
    row = result.first()
    
    return {
        "run_id": research_id,
        "total_cost": row.total_cost or 0.0,
        "total_tokens": row.total_tokens or 0,
        "input_tokens": row.input_tokens or 0,
        "output_tokens": row.output_tokens or 0,
        "total_requests": row.total_requests or 0,
    }


@router.get("/{research_id}/usage/by-stage")
async def get_run_usage_by_stage(research_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return aggregated cost and tokens grouped by stage."""
    result = await db.execute(
        select(
            APIUsageLog.stage,
            func.sum(APIUsageLog.estimated_cost).label("cost"),
            func.sum(APIUsageLog.total_tokens).label("total_tokens"),
            func.sum(APIUsageLog.input_tokens).label("input_tokens"),
            func.sum(APIUsageLog.output_tokens).label("output_tokens"),
            func.sum(APIUsageLog.request_count).label("requests")
        )
        .where(APIUsageLog.research_run_id == research_id)
        .group_by(APIUsageLog.stage)
    )
    
    stages_data = {}
    total_cost = 0.0
    
    for row in result.all():
        cost = row.cost or 0.0
        total_cost += cost
        stages_data[row.stage] = {
            "requests": row.requests or 0,
            "input_tokens": row.input_tokens or 0,
            "output_tokens": row.output_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "cost": cost
        }
        
    return {
        "stages": stages_data,
        "total": {
            "cost": total_cost
        }
    }
