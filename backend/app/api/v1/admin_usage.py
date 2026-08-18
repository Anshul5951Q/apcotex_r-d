from datetime import datetime, timedelta
from typing import List, Optional
import uuid

import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc, or_, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.api_usage_log import APIUsageLog
from app.models.research_run import ResearchRun
from app.dependencies.auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/usage", tags=["admin-telemetry"])


from datetime import timezone

async def _apply_time_filter(query, time_filter: str, db: AsyncSession, time_col=APIUsageLog.created_at):
    now = datetime.now(timezone.utc)
    if time_filter == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        reset_q = select(APIUsageLog).where(
            APIUsageLog.provider == "RESET_BASELINE",
            APIUsageLog.created_at >= start
        ).order_by(desc(APIUsageLog.created_at)).limit(1)
        res = await db.execute(reset_q)
        reset_log = res.scalar_one_or_none()
        if reset_log:
            start = reset_log.created_at
    elif time_filter == "7d":
        start = now - timedelta(days=7)
    elif time_filter == "28d":
        start = now - timedelta(days=28)
    elif time_filter == "this_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif time_filter == "last_month":
        # First day of this month
        this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Last day of last month
        end = this_month - timedelta(seconds=1)
        # First day of last month
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(time_col <= end)
    else:
        # Default: 28 days
        start = now - timedelta(days=28)
        
    query = query.filter(time_col >= start)
    return query

@router.post("/reset-today")
async def reset_today_usage(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Inserts a baseline marker to reset 'Today' metrics."""
    new_log = APIUsageLog(
        stage="RESET",
        provider="RESET_BASELINE",
        model="",
        operation="RESET_USAGE",
        status="SUCCESS",
        request_count=0
    )
    db.add(new_log)
    await db.commit()
    return {"message": "Today's usage metrics have been reset."}


@router.get("/summary")
async def get_usage_summary(
    time_filter: str = Query("28d", description="Time filter (today, 7d, 28d, this_month, last_month)"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Overall token and cost summary"""
    q = select(
        func.sum(APIUsageLog.input_tokens).label("total_input_tokens"),
        func.sum(APIUsageLog.output_tokens).label("total_output_tokens"),
        func.sum(APIUsageLog.total_tokens).label("total_tokens"),
        func.sum(APIUsageLog.request_count).label("total_calls"),
        func.sum(APIUsageLog.estimated_cost).label("total_cost"),
    )
    
    q_llm = q.filter(APIUsageLog.provider.notin_(["serper", "serper.dev", "RESET_BASELINE"]))
    q_llm = await _apply_time_filter(q_llm, time_filter, db)
    
    q_serper = select(
        func.sum(APIUsageLog.request_count).label("total_calls"),
        func.sum(APIUsageLog.estimated_cost).label("total_cost")
    ).filter(APIUsageLog.provider.in_(["serper", "serper.dev"]))
    q_serper = await _apply_time_filter(q_serper, time_filter, db)

    res_llm = await db.execute(q_llm)
    row_llm = res_llm.fetchone()
    
    res_serper = await db.execute(q_serper)
    row_serper = res_serper.fetchone()

    return {
        "llm_input_tokens": int(row_llm.total_input_tokens or 0) if row_llm else 0,
        "llm_output_tokens": int(row_llm.total_output_tokens or 0) if row_llm else 0,
        "llm_total_tokens": int(row_llm.total_tokens or 0) if row_llm else 0,
        "llm_calls": int(row_llm.total_calls or 0) if row_llm else 0,
        "serper_requests": int(row_serper.total_calls or 0) if row_serper else 0,
        "estimated_cost": float((row_llm.total_cost or 0) if row_llm else 0) + float((row_serper.total_cost or 0) if row_serper else 0)
    }



@router.get("/by-provider")
async def get_usage_by_provider(
    time_filter: str = Query("28d"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Breakdown by provider"""
    q = select(
        APIUsageLog.provider,
        func.count(func.distinct(APIUsageLog.metadata_json['logical_call_id'].astext)).label("logical_calls"),
        func.sum(APIUsageLog.request_count).label("provider_attempts"),
        func.sum(case((APIUsageLog.status == "success", 1), else_=0)).label("successful_attempts"),
        func.sum(case((APIUsageLog.status != "success", 1), else_=0)).label("failed_attempts"),
        func.sum(APIUsageLog.input_tokens).label("input_tokens"),
        func.sum(APIUsageLog.output_tokens).label("output_tokens"),
        func.sum(APIUsageLog.estimated_cost).label("cost")
    ).group_by(APIUsageLog.provider)
    q = q.filter(APIUsageLog.provider != "RESET_BASELINE")
    q = await _apply_time_filter(q, time_filter, db)
    
    res = await db.execute(q)
    results = []
    for row in res.fetchall():
        is_serper = row.provider in ["serper", "serper.dev"]
        results.append({
            "provider": row.provider,
            "logical_calls": int(row.provider_attempts) if is_serper else int(row.logical_calls or 0),
            "provider_attempts": int(row.provider_attempts or 0),
            "successful_attempts": int(row.successful_attempts or 0),
            "failed_attempts": int(row.failed_attempts or 0),
            "input_tokens": None if is_serper else int(row.input_tokens or 0),
            "output_tokens": None if is_serper else int(row.output_tokens or 0),
            "cost": float(row.cost or 0)
        })
        
    return results


@router.get("/by-stage")
async def get_usage_by_stage(
    time_filter: str = Query("28d"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Breakdown by pipeline stage"""
    q = select(
        APIUsageLog.stage,
        func.coalesce(func.count(func.distinct(
            case((APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.metadata_json['logical_call_id'].astext), else_=None)
        )), 0).label("logical_llm_calls"),
        func.coalesce(func.sum(case((APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.request_count), else_=0)), 0).label("provider_attempts"),
        func.coalesce(func.sum(case((APIUsageLog.provider.in_(["serper", "serper.dev"]), APIUsageLog.request_count), else_=0)), 0).label("serper_requests"),
        func.coalesce(func.sum(case((and_(APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.status == "success"), 1), else_=0)), 0).label("successful_attempts"),
        func.coalesce(func.sum(case((and_(APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.status != "success"), 1), else_=0)), 0).label("failed_attempts"),
        func.coalesce(func.sum(APIUsageLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(APIUsageLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(APIUsageLog.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(APIUsageLog.estimated_cost), 0).label("cost"),
        func.coalesce(func.avg(APIUsageLog.latency_ms), 0).label("avg_latency"),
    ).group_by(APIUsageLog.stage)
    q = q.filter(APIUsageLog.provider != "RESET_BASELINE")
    q = await _apply_time_filter(q, time_filter, db)
    
    logger.info(f"ADMIN USAGE BY-STAGE\nTime Filter: {time_filter}")
    
    try:
        res = await db.execute(q)
        results = []
        
        total_input = 0
        total_output = 0
        total_llm_calls = 0
        total_serper_requests = 0
        total_cost = 0.0
        
        for row in res.fetchall():
            results.append({
                "stage": row.stage,
                "logical_llm_calls": int(row.logical_llm_calls),
                "provider_attempts": int(row.provider_attempts),
                "successful_attempts": int(row.successful_attempts),
                "failed_attempts": int(row.failed_attempts),
                "serper_requests": int(row.serper_requests),
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.total_tokens),
                "cost": float(row.cost),
                "avg_latency": float(row.avg_latency)
            })
            total_input += int(row.input_tokens)
            total_output += int(row.output_tokens)
            total_llm_calls += int(row.logical_llm_calls)
            total_serper_requests += int(row.serper_requests)
            total_cost += float(row.cost)
            
        logger.info(f"STAGE USAGE RESULT\nRows: {len(results)}\nTotal Input Tokens: {total_input}\nTotal Output Tokens: {total_output}\nTotal Logical LLM Calls: {total_llm_calls}\nTotal Serper Requests: {total_serper_requests}\nTotal Cost: {total_cost}")
        
    except Exception as e:
        logger.error(f"STAGE USAGE ERROR\nException: {str(e)}\nEndpoint: /by-stage\nTime Filter: {time_filter}", exc_info=True)
        raise
        
    return results


@router.get("/by-run")
async def get_usage_by_run(
    time_filter: str = Query("28d"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Breakdown by research run"""
    q_runs = select(
        ResearchRun.id,
        ResearchRun.compound_name,
        ResearchRun.created_at,
        ResearchRun.status,
    ).order_by(desc(ResearchRun.created_at))
    q_runs = await _apply_time_filter(q_runs, time_filter, db, time_col=ResearchRun.created_at)
    
    # Paginate runs
    total_q = select(func.count()).select_from(q_runs.subquery())
    total_res = await db.execute(total_q)
    total_runs = total_res.scalar() or 0
    
    res_runs = await db.execute(q_runs.offset((page - 1) * page_size).limit(page_size))
    runs = res_runs.fetchall()
    
    results = []
    for r in runs:
        # Get token usage for this run
        q_usage = select(
            func.coalesce(func.sum(APIUsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(APIUsageLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(APIUsageLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(case((APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.request_count), else_=0)), 0).label("llm_calls"),
            func.coalesce(func.sum(case((APIUsageLog.provider.in_(["serper", "serper.dev"]), APIUsageLog.request_count), else_=0)), 0).label("serper_requests"),
            func.coalesce(func.sum(APIUsageLog.estimated_cost), 0).label("cost")
        ).filter(APIUsageLog.research_run_id == r.id)
        
        usage_res = await db.execute(q_usage)
        u = usage_res.fetchone()
        
        results.append({
            "run_id": str(r.id),
            "compound_name": r.compound_name,
            "created_at": r.created_at,
            "status": r.status.value if hasattr(r.status, 'value') else r.status,
            "input_tokens": int(u.input_tokens or 0) if u else 0,
            "output_tokens": int(u.output_tokens or 0) if u else 0,
            "total_tokens": int(u.total_tokens or 0) if u else 0,
            "llm_calls": int(u.llm_calls or 0) if u else 0,
            "serper_requests": int(u.serper_requests or 0) if u else 0,
            "cost": float(u.cost or 0) if u else 0
        })
        
    return {
        "items": results,
        "total": total_runs,
        "page": page,
        "page_size": page_size
    }


@router.get("/run/{run_id}")
async def get_usage_for_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Detailed stage breakdown for a specific run"""
    q_run = select(ResearchRun).filter(ResearchRun.id == run_id)
    res_run = await db.execute(q_run)
    run = res_run.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    q = select(
        APIUsageLog.stage,
        func.coalesce(func.count(func.distinct(
            case((APIUsageLog.provider.notin_(["serper", "serper.dev"]), func.jsonb_extract_path_text(APIUsageLog.metadata_json, 'logical_call_id')), else_=None)
        )), 0).label("logical_llm_calls"),
        func.coalesce(func.sum(case((APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.request_count), else_=0)), 0).label("provider_attempts"),
        func.coalesce(func.sum(case((APIUsageLog.provider.in_(["serper", "serper.dev"]), APIUsageLog.request_count), else_=0)), 0).label("serper_requests"),
        func.coalesce(func.sum(case((and_(APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.status == "success"), 1), else_=0)), 0).label("successful_attempts"),
        func.coalesce(func.sum(case((and_(APIUsageLog.provider.notin_(["serper", "serper.dev"]), APIUsageLog.status != "success"), 1), else_=0)), 0).label("failed_attempts"),
        func.coalesce(func.sum(APIUsageLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(APIUsageLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(APIUsageLog.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(APIUsageLog.estimated_cost), 0).label("cost"),
        func.coalesce(func.avg(APIUsageLog.latency_ms), 0).label("avg_latency"),
    ).filter(APIUsageLog.research_run_id == run_id).group_by(APIUsageLog.stage)
    
    res = await db.execute(q)
    
    stage_data = {
        row.stage: {
            "stage": row.stage,
            "logical_llm_calls": int(row.logical_llm_calls),
            "provider_attempts": int(row.provider_attempts),
            "successful_attempts": int(row.successful_attempts),
            "failed_attempts": int(row.failed_attempts),
            "serper_requests": int(row.serper_requests),
            "input_tokens": int(row.input_tokens),
            "output_tokens": int(row.output_tokens),
            "total_tokens": int(row.total_tokens),
            "cost": float(row.cost),
            "avg_latency": float(row.avg_latency)
        } for row in res.fetchall()
    }
    
    expected_stages = [
        "QUERY_EXPANSION",
        "PATENT_SEARCH",
        "TITLE_SELECTION",
        "PATENT_EXTRACTION",
        "VALIDATION",
        "EVIDENCE_COMPACTION",
        "REPORT_GENERATION"
    ]
    
    stages = []
    
    total_input = 0
    total_output = 0
    total_cost = 0.0
    total_llm_calls = 0
    total_serper_requests = 0
    
    for stg in expected_stages:
        if stg in stage_data:
            s = stage_data[stg]
            stages.append(s)
            total_input += s["input_tokens"]
            total_output += s["output_tokens"]
            total_cost += s["cost"]
            total_llm_calls += s["logical_llm_calls"]
            total_serper_requests += s["serper_requests"]
        else:
            stages.append({
                "stage": stg,
                "logical_llm_calls": 0,
                "provider_attempts": 0,
                "successful_attempts": 0,
                "failed_attempts": 0,
                "serper_requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "avg_latency": 0.0
            })
            
    query_exp_calls = stage_data.get("QUERY_EXPANSION", {}).get("logical_llm_calls", 0)
    report_gen_calls = stage_data.get("REPORT_GENERATION", {}).get("logical_llm_calls", 0)
    validation_calls = stage_data.get("VALIDATION", {}).get("logical_llm_calls", 0)
    extraction_calls = stage_data.get("PATENT_EXTRACTION", {}).get("logical_llm_calls", 0)
    
    architecture_violation = None
    if query_exp_calls > 1 or report_gen_calls > 1 or validation_calls != 0 or extraction_calls != 0:
        architecture_violation = "VIOLATION: Strict limits exceeded. Query Expansion and Report Generation must be <= 1. Validation and Extraction must be 0."
            
    return {
        "run_id": str(run.id),
        "compound_name": run.compound_name,
        "status": run.status.value if hasattr(run.status, 'value') else run.status,
        "created_at": run.created_at,
        "architecture_violation": architecture_violation,
        "total": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "llm_calls": total_llm_calls,
            "serper_requests": total_serper_requests,
            "cost": total_cost,
        },
        "stages": stages
    }


@router.get("/calls")
async def get_individual_calls(
    time_filter: str = Query("28d"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    run_id: Optional[uuid.UUID] = None,
    provider: Optional[str] = None,
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Detailed individual API calls"""
    q = select(APIUsageLog).order_by(desc(APIUsageLog.created_at))
    q = _apply_time_filter(q, time_filter)
    
    if run_id:
        q = q.filter(APIUsageLog.research_run_id == run_id)
    if provider:
        q = q.filter(APIUsageLog.provider == provider)
    if stage:
        q = q.filter(APIUsageLog.stage == stage)
        
    total_q = select(func.count()).select_from(q.subquery())
    total_res = await db.execute(total_q)
    total_calls = total_res.scalar() or 0
    
    res = await db.execute(q.offset((page - 1) * page_size).limit(page_size))
    calls = res.scalars().all()
    
    return {
        "items": [
            {
                "id": str(c.id),
                "timestamp": c.created_at,
                "stage": c.stage,
                "provider": c.provider,
                "model": c.model,
                "operation": c.operation,
                "input_tokens": c.input_tokens,
                "output_tokens": c.output_tokens,
                "total_tokens": c.total_tokens,
                "latency_ms": c.latency_ms,
                "status": c.status,
                "cost": c.estimated_cost,
                "error_message": c.error_message
            }
            for c in calls
        ],
        "total": total_calls,
        "page": page,
        "page_size": page_size
    }
