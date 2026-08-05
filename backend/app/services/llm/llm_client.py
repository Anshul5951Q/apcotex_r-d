"""
app/services/llm/llm_client.py

Centralized LLM abstraction that dynamically resolves the configured LLM provider from the database.
All services communicate with this singleton.
"""
import logging
from typing import Type

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.app_config import AppConfig
from app.services.llm.base import T
from app.services.llm.provider_registry import instantiate_provider, PROVIDER_DEFINITIONS

logger = logging.getLogger(__name__)

class DynamicLLMClient:
    async def _get_active_provider(self):
        """Fetches the currently configured LLM provider from the DB."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AppConfig).where(AppConfig.key == "active_llm_provider"))
            config = result.scalar_one_or_none()
            
            provider_id = "gemini" # Default
            if config and isinstance(config.value, dict) and "provider_id" in config.value:
                provider_id = config.value["provider_id"]
                
            try:
                provider = instantiate_provider(provider_id)
                logger.info("[LLM] Dynamically resolved provider: %s", PROVIDER_DEFINITIONS.get(provider_id, {}).get("name", provider_id))
                return provider
            except Exception as e:
                logger.error("[LLM] Failed to instantiate provider '%s': %s. Falling back to Gemini.", provider_id, e)
                return instantiate_provider("gemini")

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        provider = await self._get_active_provider()
        return await provider.generate_text(prompt, system_prompt, temperature)

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1) -> T | None:
        provider = await self._get_active_provider()
        return await provider.generate_structured(prompt, system_prompt, schema, temperature)

# Singleton instance for easy importing
llm_client = DynamicLLMClient()
