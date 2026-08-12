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
    LLMProviderUnavailableError, LLMInvalidRequestError
)
from app.services.llm.provider_registry import instantiate_provider, PROVIDER_DEFINITIONS

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
        self.semaphore = asyncio.Semaphore(3) # Centralized rate limiting

    async def _get_available_provider(self) -> tuple[str, Any]:
        """Fetches the first available configured LLM provider, avoiding disabled ones."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AppConfig).where(AppConfig.key == "active_llm_provider"))
            config = result.scalar_one_or_none()
            
            # Precedence 1: UI / DB Setting
            # Precedence 2: Environment settings.PRIMARY_LLM
            preferred_provider = settings.PRIMARY_LLM
            
            if config and isinstance(config.value, dict):
                if "provider_id" in config.value:
                    preferred_provider = config.value["provider_id"]
                
            logger.info("[LLM] Primary provider: %s", preferred_provider)
                
            # Precedence 3: Environment settings.FALLBACK_LLM
            fallback_order = [preferred_provider]
            
            if settings.ENABLE_FALLBACK and settings.FALLBACK_LLM and settings.FALLBACK_LLM != preferred_provider:
                fallback_order.append(settings.FALLBACK_LLM)
            
            for provider_id in fallback_order:
                if provider_id in self.disabled_providers:
                    continue
                    
                try:
                    provider = instantiate_provider(provider_id)
                    logger.info("[LLM] Selected provider: %s", provider_id)
                    return provider_id, provider
                except ValueError as ve:
                    if "Missing API Key" in str(ve) or "not configured" in str(ve):
                        logger.info("[LLM] %s fallback disabled: API key not configured", provider_id.capitalize())
                    else:
                        logger.warning("[LLM] Failed to instantiate provider '%s': %s", provider_id, ve)
                    self.disabled_providers.add(provider_id)
                except Exception as e:
                    logger.warning("[LLM] Failed to instantiate provider '%s': %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
            
            # If we fall out of the loop
            raise ProviderExhaustedException(f"All configured LLM providers exhausted. Primary was: {preferred_provider}")

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        provider_id, provider = await self._get_available_provider()
        
        # Calculate token estimate
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
            token_count = len(encoder.encode(prompt + system_prompt))
        except Exception:
            token_count = len(prompt) // 4
            
        start_time = time.time()
        logger.info("[LLM] Executing request with %s (approx %d tokens)...", provider_id, token_count)
        
        max_retries = 2
        base_delay = 2.0
        
        for attempt in range(max_retries + 1):
            try:
                async with self.semaphore:
                    result = await provider.generate_text(prompt, system_prompt, temperature)
                duration = time.time() - start_time
                logger.info("[LLM] Request completed in %.2f seconds.", duration)
                return result
            except Exception as e:
                if isinstance(e, LLMModelUnavailableError):
                    logger.error("[LLM] Model unavailable for %s: %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    raise ProviderExhaustedException(f"Provider {provider_id} model unavailable: {e}")
                elif isinstance(e, LLMQuotaExhaustedError):
                    logger.error("[LLM] Hard quota exhausted for %s: %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    raise ProviderExhaustedException(f"Provider Quota exhausted for {provider_id}")
                elif isinstance(e, LLMRateLimitError):
                    if attempt < max_retries:
                        delay = getattr(e, "retry_after", None) or (base_delay * (2 ** attempt) + random.uniform(0, 1))
                        logger.warning("[LLM] %s rate limit (%s). Retrying in %.2f sec (Attempt %d/%d)", provider_id, getattr(e, "quota_type", "UNKNOWN_429"), delay, attempt+1, max_retries)
                        await asyncio.sleep(delay)
                    else:
                        logger.error("[LLM] Max retries reached for %s rate limit. Failing gracefully.", provider_id)
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
                    # For fatal errors, we disable the provider and try another
                    self.disabled_providers.add(provider_id)
                    return await self.generate_text(prompt, system_prompt, temperature)
                    
        raise LLMRateLimitError("Rate limited.")

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1) -> tuple[T | None, str]:
        provider_id, provider = await self._get_available_provider()
        
        # Calculate token estimate
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
            token_count = len(encoder.encode(prompt + system_prompt))
        except Exception:
            token_count = len(prompt) // 4
            
        start_time = time.time()
        logger.info("[LLM] Executing structured request with %s (approx %d tokens)...", provider_id, token_count)
        
        max_retries = 2
        base_delay = 2.0
        
        for attempt in range(max_retries + 1):
            try:
                async with self.semaphore:
                    result = await provider.generate_structured(prompt, system_prompt, schema, temperature)
                duration = time.time() - start_time
                logger.info("[LLM] Structured request completed in %.2f seconds.", duration)
                return result, provider_id
            except Exception as e:
                if isinstance(e, LLMModelUnavailableError):
                    logger.error("[LLM] Model unavailable for %s: %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    raise ProviderExhaustedException(f"Provider {provider_id} model unavailable: {e}")
                elif isinstance(e, LLMQuotaExhaustedError):
                    logger.error("[LLM] Hard quota exhausted for %s: %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
                    raise ProviderExhaustedException(f"Provider Quota exhausted for {provider_id}")
                elif isinstance(e, LLMRateLimitError):
                    if attempt < max_retries:
                        delay = getattr(e, "retry_after", None) or (base_delay * (2 ** attempt) + random.uniform(0, 1))
                        logger.warning("[LLM] %s rate limit (%s). Retrying in %.2f sec (Attempt %d/%d)", provider_id, getattr(e, "quota_type", "UNKNOWN_429"), delay, attempt+1, max_retries)
                        await asyncio.sleep(delay)
                    else:
                        logger.error("[LLM] Max retries reached for %s rate limit. Failing gracefully.", provider_id)
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
                    # For fatal errors, we disable the provider and try another
                    self.disabled_providers.add(provider_id)
                    return await self.generate_structured(prompt, system_prompt, schema, temperature)
                    
        raise LLMRateLimitError("Rate limited.")

# Singleton instance for easy importing
llm_client = DynamicLLMClient()
