"""
app/services/llm/llm_client.py

Centralized LLM abstraction that dynamically resolves the configured LLM provider from the database.
All services communicate with this singleton.
"""
import logging
import time
import asyncio
import random
from typing import Type, Any
import tiktoken

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.app_config import AppConfig
from app.core.config import settings
from app.services.llm.base import (
    T, 
    LLMAuthenticationError, LLMModelUnavailableError,
    LLMRateLimitError, LLMQuotaExhaustedError, 
    LLMProviderUnavailableError, LLMInvalidRequestError,
    LLMInvalidResponseError
)
from app.services.llm.provider_registry import instantiate_provider, PROVIDER_DEFINITIONS
from app.services.usage_logger import UsageLogger
from app.core.telemetry import get_current_run_id, get_current_stage

logger = logging.getLogger(__name__)

class ProviderExhaustedException(Exception):
    """Raised when all configured LLM providers have been disabled due to fatal errors."""
    pass

class LLMRateLimitException(Exception):
    """Raised when an LLM provider fails due to rate limits after maximum retries."""
    pass

class DynamicLLMClient:
    def __init__(self):
        self.disabled_providers = set()
        self.provider_health = {}
        self.semaphore = asyncio.Semaphore(3) # Centralized rate limiting

    def reset_health(self):
        self.disabled_providers.clear()
        self.provider_health.clear()
        logger.info("[LLM] Provider health state reset for new run.")

    async def _get_available_provider(self) -> tuple[str, Any]:
        """Fetches the first available configured LLM provider, avoiding disabled ones."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AppConfig).where(AppConfig.key == "active_llm_provider"))
            config = result.scalar_one_or_none()

            preferred_provider = settings.PRIMARY_LLM
            if config and isinstance(config.value, dict) and "provider_id" in config.value:
                preferred_provider = config.value["provider_id"]

            fallback_order = [preferred_provider]
            if settings.ENABLE_FALLBACK and settings.FALLBACK_LLM and settings.FALLBACK_LLM != preferred_provider:
                fallback_order.append(settings.FALLBACK_LLM)

            for provider_id in fallback_order:
                if provider_id in self.disabled_providers:
                    logger.debug("[LLM] Skipping disabled provider: %s", provider_id)
                    continue
                try:
                    provider = instantiate_provider(provider_id)
                    logger.debug("[LLM] Selected provider: %s", provider_id)
                    return provider_id, provider
                except ValueError as ve:
                    if "Missing API Key" in str(ve) or "not configured" in str(ve):
                        logger.debug("[LLM] %s disabled: API key not configured", provider_id)
                    else:
                        logger.warning("[LLM] Failed to instantiate '%s': %s", provider_id, ve)
                    self.disabled_providers.add(provider_id)
                except Exception as e:
                    logger.warning("[LLM] Failed to instantiate '%s': %s", provider_id, e)
                    self.disabled_providers.add(provider_id)

            raise ProviderExhaustedException(
                f"All configured LLM providers exhausted. Primary was: {preferred_provider}. "
                f"Disabled: {self.disabled_providers}"
            )

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        import uuid
        logical_call_id = str(uuid.uuid4())
        provider_id, provider = await self._get_available_provider()
        
        # Calculate token estimate
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
            token_count = len(encoder.encode(prompt + system_prompt))
        except Exception:
            token_count = len(prompt) // 4
            
        start_time = time.time()
        model_name = getattr(provider, 'model_name', 'UNKNOWN')
        
        logger.info("=" * 60)
        logger.info(f"LLM REQUEST INITIATED: UNKNOWN ({model_name}) | Tokens: {token_count} (est)")
        logger.info("=" * 60)
        max_retries = 2
        base_delay = 2.0
        
        for attempt in range(max_retries + 1):
            try:
                async with self.semaphore:
                    result, usage = await provider.generate_text(prompt, system_prompt, temperature)
                duration = time.time() - start_time
                in_tokens = usage.get("input_tokens") or token_count
                out_tokens = usage.get("output_tokens") or 0
                tot_tokens = in_tokens + out_tokens
                
                run_id = get_current_run_id() or "UNKNOWN"
                stage = getattr(get_current_stage(), 'value', None) or "UNKNOWN"
                
                logger.info("LLM REQUEST")
                logger.info("-" * 11)
                logger.info(f"Run ID: {run_id}")
                logger.info(f"Stage: {stage}")
                logger.info(f"Provider: {provider_id.upper()}")
                logger.info(f"Model: {model_name}")
                logger.info(f"Request Type: TEXT")
                logger.info(f"Attempt: {attempt + 1}")
                logger.info(f"Input Tokens: {in_tokens}")
                logger.info(f"Output Tokens: {out_tokens}")
                logger.info(f"Total Tokens: {tot_tokens}")
                logger.info(f"Estimated Cost: N/A")
                logger.info(f"Latency: {duration:.2f}s")
                logger.info(f"Status: SUCCESS")
                logger.info(f"Error Type: NONE")
                logger.info("=" * 60)
                # Log success
                await UsageLogger.record_api_usage(
                    provider=provider_id,
                    operation="generate_text",
                    model=getattr(provider, 'model_name', None),
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    latency_ms=int(duration * 1000),
                    status="success",
                    retry_count=attempt,
                    metadata={"logical_call_id": logical_call_id}
                )
                
                return result
            except Exception as e:
                if isinstance(e, LLMModelUnavailableError):
                    logger.error("[LLM] Model unavailable for %s: %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    raise ProviderExhaustedException(f"Provider {provider_id} model unavailable: {e}")
                elif isinstance(e, LLMQuotaExhaustedError):
                    logger.info("=" * 60)
                    logger.info("LLM DAILY QUOTA EXHAUSTED")
                    logger.info("-" * 25)
                    logger.info(f"Provider: {provider_id.upper()}")
                    logger.info(f"Requested Tokens: {token_count} (est)")
                    logger.info(f"Status: FAILED")
                    logger.info("=" * 60)
                    self.disabled_providers.add(provider_id)
                    
                    duration = time.time() - start_time
                    await UsageLogger.record_api_usage(
                        provider=provider_id,
                        operation="generate_text",
                        model=getattr(provider, 'model_name', None),
                        input_tokens=token_count,
                        latency_ms=int(duration * 1000),
                        status="failed",
                        error_type=type(e).__name__,
                        error_message=str(e),
                        retry_count=attempt,
                        metadata={"logical_call_id": logical_call_id}
                    )
                    
                    raise ProviderExhaustedException(f"Provider Quota exhausted for {provider_id}")
                elif isinstance(e, LLMRateLimitError):
                    if attempt < max_retries:
                        delay = getattr(e, "retry_after", None) or (base_delay * (2 ** attempt) + random.uniform(0, 1))
                        logger.warning("[LLM] %s rate limit (%s). Retrying in %.2f sec (Attempt %d/%d)", provider_id, getattr(e, "quota_type", "UNKNOWN_429"), delay, attempt+1, max_retries)
                        await asyncio.sleep(delay)
                    else:
                        logger.error("[LLM] Max retries reached for %s rate limit. Failing gracefully.", provider_id)
                        
                        run_id = get_current_run_id() or "UNKNOWN"
                        stage = getattr(get_current_stage(), 'value', None) or "UNKNOWN"
                        
                        logger.info("LLM REQUEST")
                        logger.info("-" * 11)
                        logger.info(f"Run ID: {run_id}")
                        logger.info(f"Stage: {stage}")
                        logger.info(f"Provider: {provider_id.upper()}")
                        logger.info(f"Model: {model_name}")
                        logger.info(f"Request Type: TEXT")
                        logger.info(f"Attempt: {attempt + 1}")
                        logger.info(f"Input Tokens: {token_count} (est)")
                        logger.info(f"Output Tokens: 0")
                        logger.info(f"Total Tokens: {token_count}")
                        logger.info(f"Estimated Cost: N/A")
                        logger.info(f"Latency: {time.time() - start_time:.2f}s")
                        logger.info(f"Status: FAILED")
                        logger.info(f"Error Type: RATE_LIMITED")
                        logger.info("=" * 60)
                        
                        raise LLMRateLimitError(f"Rate limited by {provider_id} after {max_retries} attempts.")
                elif isinstance(e, LLMAuthenticationError):
                    logger.error("[LLM] Authentication failed for %s: %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    raise ProviderExhaustedException(f"Provider {provider_id} authentication failed: {e}")
                elif isinstance(e, LLMInvalidRequestError):
                    logger.error("[LLM] Invalid request sent to %s: %s", provider_id, e)
                    raise e # Don't disable provider for a bad prompt, just fail
                else:
                    logger.error("[LLM] Fatal error from %s: %s", provider_id, e)
                    
                    # Log failure
                    duration = time.time() - start_time
                    await UsageLogger.record_api_usage(
                        provider=provider_id,
                        operation="generate_text",
                        model=getattr(provider, 'model_name', None),
                        input_tokens=token_count, # Estimated
                        latency_ms=int(duration * 1000),
                        status="failed",
                        error_type=type(e).__name__,
                        error_message=str(e),
                        retry_count=attempt,
                        metadata={"logical_call_id": logical_call_id}
                    )
                    
                    # For fatal errors, we disable the provider and try another
                    self.disabled_providers.add(provider_id)
                    return await self.generate_text(prompt, system_prompt, temperature)
                    
        raise LLMRateLimitError("Rate limited.")

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1, metadata: dict | None = None) -> tuple[T | None, str, dict]:
        import uuid
        logical_call_id = str(uuid.uuid4())
        provider_id, provider = await self._get_available_provider()
        metadata = metadata or {}

        try:
            encoder = tiktoken.get_encoding("cl100k_base")
            token_count = len(encoder.encode(prompt + system_prompt))
        except Exception:
            token_count = len(prompt) // 4

        start_time = time.time()
        model_name = getattr(provider, 'model_name', 'UNKNOWN')
        stage_val = metadata.get('stage') or getattr(get_current_stage(), 'value', None) or "UNKNOWN"
        schema_name = schema.__name__ if schema else 'UNKNOWN'

        logger.info("[LLM] %s | %s | %s | ~%d tokens", stage_val, provider_id, schema_name, token_count)

        max_retries = 5   # 503/429 can need 30-90s to clear; 5 retries with exponential backoff
        base_delay = 10.0  # 10s → 20s → 40s → 80s → 160s

        for attempt in range(max_retries + 1):
            try:
                async with self.semaphore:
                    result, usage = await provider.generate_structured(prompt, system_prompt, schema, temperature)
                duration = time.time() - start_time
                in_tokens = usage.get("input_tokens") or token_count
                out_tokens = usage.get("output_tokens") or 0

                logger.info(
                    "[LLM] OK | %s | %s | in=%d out=%d lat=%.1fs",
                    stage_val, provider_id, in_tokens, out_tokens, duration
                )

                await UsageLogger.record_api_usage(
                    provider=provider_id,
                    operation="generate_structured",
                    model=model_name,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    latency_ms=int(duration * 1000),
                    status="success",
                    retry_count=attempt,
                    metadata={"schema_name": schema_name, "logical_call_id": logical_call_id}
                )
                return result, provider_id, usage

            except Exception as e:
                from pydantic import ValidationError as PydanticValidationError
                duration = time.time() - start_time

                if isinstance(e, PydanticValidationError):
                    failed_usage = getattr(e, '_failed_usage', {})
                    logger.warning(
                        "[LLM] VALIDATION_FAILED | %s | %s | schema=%s | lat=%.1fs",
                        stage_val, provider_id, schema_name, duration
                    )
                    await UsageLogger.record_api_usage(
                        provider=provider_id, operation="generate_structured", model=model_name,
                        input_tokens=failed_usage.get("input_tokens") or token_count,
                        output_tokens=failed_usage.get("output_tokens") or 0,
                        latency_ms=int(duration * 1000), status="validation_failed",
                        error_type="ValidationError", error_message=str(e)[:500],
                        retry_count=attempt, metadata={"schema_name": schema_name, "logical_call_id": logical_call_id}
                    )
                    # Validation error is a per-request failure — do NOT disable provider
                    return None, provider_id, failed_usage

                elif isinstance(e, LLMInvalidResponseError):
                    # Malformed/empty response is a per-request content error.
                    # Do NOT disable the provider — the next patent should still be able to use it.
                    logger.warning(
                        "[LLM] INVALID_RESPONSE | %s | %s | %s | lat=%.1fs — provider kept enabled",
                        stage_val, provider_id, str(e)[:120], duration
                    )
                    await UsageLogger.record_api_usage(
                        provider=provider_id, operation="generate_structured", model=model_name,
                        input_tokens=token_count, latency_ms=int(duration * 1000),
                        status="failed", error_type="LLMInvalidResponseError",
                        error_message=str(e)[:300], retry_count=attempt,
                        metadata={"schema_name": schema_name, "logical_call_id": logical_call_id}
                    )
                    return None, provider_id, {}

                elif isinstance(e, LLMModelUnavailableError):
                    logger.error("[LLM] MODEL_UNAVAILABLE | %s | %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    return await self.generate_structured(prompt, system_prompt, schema, temperature, metadata)

                elif isinstance(e, LLMQuotaExhaustedError):
                    logger.error(
                        "[LLM] QUOTA_EXHAUSTED | %s | ~%d tokens | disabling provider",
                        provider_id, token_count
                    )
                    self.disabled_providers.add(provider_id)
                    await UsageLogger.record_api_usage(
                        provider=provider_id, operation="generate_structured", model=model_name,
                        input_tokens=token_count, latency_ms=int(duration * 1000),
                        status="failed", error_type=type(e).__name__, error_message=str(e),
                        retry_count=attempt, metadata={"schema_name": schema_name, "logical_call_id": logical_call_id}
                    )
                    return await self.generate_structured(prompt, system_prompt, schema, temperature, metadata)

                elif isinstance(e, LLMRateLimitError):
                    if attempt < max_retries:
                        delay = getattr(e, "retry_after", None) or (base_delay * (2 ** attempt) + random.uniform(0, 1))
                        logger.warning(
                            "[LLM] RATE_LIMITED | %s | quota_type=%s | retry in %.1fs (%d/%d)",
                            provider_id, getattr(e, 'quota_type', 'UNKNOWN'), delay, attempt + 1, max_retries
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error("[LLM] RATE_LIMITED | %s | max retries reached", provider_id)
                        raise LLMRateLimitError(f"Rate limited by {provider_id} after {max_retries} retries.")

                elif isinstance(e, LLMAuthenticationError):
                    logger.error("[LLM] AUTH_FAILED | %s | %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    raise ProviderExhaustedException(f"Provider {provider_id} authentication failed: {e}")

                elif isinstance(e, LLMInvalidRequestError):
                    logger.error("[LLM] INVALID_REQUEST | %s | %s", provider_id, str(e)[:200])
                    # Don't disable provider for a bad prompt — this is a caller error
                    raise e

                else:
                    # Generic/unexpected error — do NOT disable provider for extraction calls.
                    # Log and return None so this single patent fails but others can continue.
                    logger.error(
                        "[LLM] UNEXPECTED_ERROR | %s | %s | %s | lat=%.1fs",
                        stage_val, provider_id, type(e).__name__, duration
                    )
                    await UsageLogger.record_api_usage(
                        provider=provider_id, operation="generate_structured", model=model_name,
                        input_tokens=token_count, latency_ms=int(duration * 1000),
                        status="failed", error_type=type(e).__name__, error_message=str(e)[:300],
                        retry_count=attempt, metadata={"schema_name": schema_name, "logical_call_id": logical_call_id}
                    )
                    return None, provider_id, {}

        raise LLMRateLimitError("Rate limited.")

# Singleton instance for easy importing
llm_client = DynamicLLMClient()
