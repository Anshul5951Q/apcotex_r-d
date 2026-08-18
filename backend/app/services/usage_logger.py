"""
app/services/usage_logger.py

Centralized service to record API and LLM usage securely without blocking core application logic.
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from app.db.session import AsyncSessionLocal
from app.models.api_usage_log import APIUsageLog
from app.core.telemetry import get_current_run_id, get_current_stage, get_current_project_id
from app.config.model_pricing import MODEL_PRICING
import asyncio

logger = logging.getLogger(__name__)

class UsageLogger:
    @staticmethod
    def _calculate_cost(provider: str, model: str, input_tokens: Optional[int], output_tokens: Optional[int], request_count: int = 1) -> tuple[Optional[float], Optional[float], Optional[float], str]:
        """Calculates input, output, and total costs based on configured pricing."""
        if provider == "serper":
            pricing = MODEL_PRICING.get("serper", {})
            cost_per_req = pricing.get("cost_per_request", 0.0)
            if cost_per_req > 0:
                total_cost = cost_per_req * request_count
                return None, None, total_cost, "configured_pricing"
            return None, None, None, "unavailable"

        pricing = MODEL_PRICING.get(model)
        if not pricing:
            # Fallback to estimated pricing if model not found but we have tokens?
            # No, return None if we don't know the price.
            return None, None, None, "unavailable"

        in_cost = None
        out_cost = None
        total_cost = 0.0
        
        if input_tokens is not None:
            in_cost = (input_tokens / 1_000_000) * pricing.get("input_per_1m_tokens", 0.0)
            total_cost += in_cost
            
        if output_tokens is not None:
            out_cost = (output_tokens / 1_000_000) * pricing.get("output_per_1m_tokens", 0.0)
            total_cost += out_cost
            
        return in_cost, out_cost, total_cost, "configured_pricing"

    @classmethod
    async def record_api_usage(
        cls,
        provider: str,
        operation: str,
        model: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        request_count: int = 1,
        latency_ms: Optional[int] = None,
        status: str = "success",
        http_status: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record API usage. Non-blocking and catches all exceptions.
        """
        try:
            # Fire and forget
            asyncio.create_task(cls._async_record_usage(
                provider=provider,
                operation=operation,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_count=request_count,
                latency_ms=latency_ms,
                status=status,
                http_status=http_status,
                error_type=error_type,
                error_message=error_message,
                retry_count=retry_count,
                metadata=metadata
            ))
        except Exception as e:
            logger.exception("Failed to dispatch telemetry task")

    @classmethod
    async def _async_record_usage(
        cls,
        provider: str,
        operation: str,
        model: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        request_count: int = 1,
        latency_ms: Optional[int] = None,
        status: str = "success",
        http_status: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        try:
            run_id = get_current_run_id()
            project_id = get_current_project_id()
            stage = get_current_stage()
            
            stage_val = stage.value if stage else "OTHER"
            
            total_tokens = None
            if input_tokens is not None and output_tokens is not None:
                total_tokens = input_tokens + output_tokens
                
            in_cost, out_cost, total_cost, usage_source = cls._calculate_cost(
                provider=provider, 
                model=model, 
                input_tokens=input_tokens, 
                output_tokens=output_tokens, 
                request_count=request_count
            )

            # Structured logging
            if provider == "serper":
                credits = metadata.get("credits", request_count) if metadata else request_count
                log_str = f"[USAGE] run_id={run_id} stage={stage_val} provider={provider} serper_credits={credits} cost={total_cost or ''} latency_ms={latency_ms or ''} status={status}"
            else:
                log_str = f"[USAGE] run_id={run_id} stage={stage_val} provider={provider} model={model or ''} " \
                          f"input_tokens={input_tokens or ''} output_tokens={output_tokens or ''} total_tokens={total_tokens or ''} " \
                          f"cost={total_cost or ''} latency_ms={latency_ms or ''} status={status}"
            logger.info(log_str)

            async with AsyncSessionLocal() as session:
                log_entry = APIUsageLog(
                    research_run_id=run_id,
                    project_id=project_id,
                    stage=stage_val,
                    provider=provider,
                    model=model,
                    operation=operation,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    input_cost=in_cost,
                    output_cost=out_cost,
                    estimated_cost=total_cost,
                    usage_source=usage_source,
                    request_count=request_count,
                    latency_ms=latency_ms,
                    status=status,
                    http_status=http_status,
                    error_type=error_type,
                    error_message=error_message[:499] if error_message else None,
                    retry_count=retry_count,
                    metadata_json=metadata or {}
                )
                session.add(log_entry)
                await session.commit()
                
        except Exception as e:
            logger.exception("Failed to save APIUsageLog to database")
