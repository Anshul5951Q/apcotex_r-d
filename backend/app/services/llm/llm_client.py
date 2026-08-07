"""
app/services/llm/llm_client.py

Centralized LLM abstraction that dynamically resolves the configured LLM provider from the database.
All services communicate with this singleton.
"""
import logging
import time
from typing import Type, Any
import tiktoken

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.app_config import AppConfig
from app.services.llm.base import T
from app.services.llm.provider_registry import instantiate_provider, PROVIDER_DEFINITIONS

logger = logging.getLogger(__name__)

class ProviderExhaustedException(Exception):
    """Raised when all configured LLM providers have been disabled due to rate limits or errors."""
    pass

class DynamicLLMClient:
    def __init__(self):
        self.disabled_providers = set()

    async def _get_available_provider(self) -> tuple[str, Any]:
        """Fetches the first available configured LLM provider, avoiding disabled ones."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AppConfig).where(AppConfig.key == "active_llm_provider"))
            config = result.scalar_one_or_none()
            
            preferred_provider = "gemini"
            auto_provider_mode = False
            
            if config and isinstance(config.value, dict):
                if "provider_id" in config.value:
                    preferred_provider = config.value["provider_id"]
                if "auto_provider_mode" in config.value:
                    auto_provider_mode = config.value["auto_provider_mode"]
                
            # Ordered fallback list
            if auto_provider_mode:
                fallback_order = [preferred_provider] + [p for p in ["gemini", "groq", "openai", "claude"] if p != preferred_provider]
            else:
                fallback_order = [preferred_provider]
            
            for provider_id in fallback_order:
                if provider_id in self.disabled_providers:
                    continue
                    
                try:
                    provider = instantiate_provider(provider_id)
                    return provider_id, provider
                except Exception as e:
                    logger.warning("[LLM] Failed to instantiate provider '%s': %s", provider_id, e)
                    self.disabled_providers.add(provider_id)
            
            if not auto_provider_mode:
                raise ProviderExhaustedException(f"Strict Provider Mode: '{preferred_provider}' failed or quota exhausted.")
            else:
                raise ProviderExhaustedException("Auto Provider Mode: All configured LLM providers exhausted.")

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
        
        try:
            result = await provider.generate_text(prompt, system_prompt, temperature)
            duration = time.time() - start_time
            logger.info("[LLM] Request completed in %.2f seconds.", duration)
            return result
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "rate limit" in str(e).lower():
                logger.warning("[LLM] %s rate limit detected: %s. Disabling provider for this run.", provider_id, e)
                self.disabled_providers.add(provider_id)
                # Recursively try the next provider
                return await self.generate_text(prompt, system_prompt, temperature)
            raise e

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
        
        try:
            result = await provider.generate_structured(prompt, system_prompt, schema, temperature)
            duration = time.time() - start_time
            logger.info("[LLM] Structured request completed in %.2f seconds.", duration)
            return result, provider_id
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "rate limit" in str(e).lower():
                logger.warning("[LLM] %s rate limit detected: %s. Disabling provider for this run.", provider_id, e)
                self.disabled_providers.add(provider_id)
                # Recursively try the next provider
                return await self.generate_structured(prompt, system_prompt, schema, temperature)
            raise e

# Singleton instance for easy importing
llm_client = DynamicLLMClient()
