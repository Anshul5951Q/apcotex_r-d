"""
app/services/llm/openai_compatible_provider.py

A unified provider for OpenAI, Grok, DeepSeek, and Qwen using the standard openai SDK.
"""
import logging
from typing import Type
import json

from openai import AsyncOpenAI, RateLimitError
from pydantic import ValidationError

from app.services.llm.base import BaseLLMProvider, LLMRateLimitError, T

logger = logging.getLogger(__name__)

class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str, model_name: str, provider_name: str):
        if not api_key:
            raise ValueError(f"{provider_name} API key is not configured.")
        
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.provider_name = provider_name

    def _handle_error(self, e: Exception):
        if isinstance(e, RateLimitError):
            err_str = str(e).lower()
            if "tokens_per_day" in err_str or "daily quota" in err_str or "budget exceeded" in err_str:
                from app.services.llm.base import LLMQuotaExhaustedError
                raise LLMQuotaExhaustedError(f"{self.provider_name} Daily Token Quota Exceeded: {e}")
            raise LLMRateLimitError(f"{self.provider_name} Rate Limit Exceeded: {e}")
        raise e

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> tuple[str, dict]:
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
            )
            usage = {}
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", None),
                    "output_tokens": getattr(response.usage, "completion_tokens", None),
                }
            return response.choices[0].message.content, usage
        except Exception as e:
            self._handle_error(e)

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1) -> tuple[T | None, dict]:
        try:
            # We use JSON mode. To make it strictly structured, we append the schema to the system prompt
            # since not all providers support strict function calling.
            schema_json = json.dumps(schema.model_json_schema(), indent=2)
            augmented_system_prompt = f"{system_prompt}\n\nYou must return valid JSON that matches this schema exactly:\n{schema_json}"
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": augmented_system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            
            usage = {}
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", None),
                    "output_tokens": getattr(response.usage, "completion_tokens", None),
                }
                
            return schema.model_validate_json(content), usage
        except ValidationError as ve:
            logger.error("Validation error extracting structured data via %s: %s", self.provider_name, ve)
            return None, {}
        except Exception as e:
            self._handle_error(e)
