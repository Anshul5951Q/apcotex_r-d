"""
app/services/llm/gemini_provider.py

Gemini implementation using google-genai.
"""
import asyncio
import logging
import re
from typing import Type

from google import genai
from google.genai.errors import APIError
from pydantic import ValidationError

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, RateLimitException, T

logger = logging.getLogger(__name__)

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("Gemini API key is not configured.")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    def _handle_error(self, e: Exception):
        if isinstance(e, APIError):
            if e.code == 429 or "Quota exceeded" in str(e):
                retry_after = None
                match = re.search(r'retry in ([\d\.]+)s', str(e))
                if match:
                    try:
                        retry_after = float(match.group(1))
                    except ValueError:
                        pass
                raise RateLimitException(f"Gemini Rate Limit / Quota Exceeded: {e}", retry_after)
        raise e

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        retries = 5
        delay = 10
        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                    ),
                )
                return response.text
            except Exception as e:
                try:
                    self._handle_error(e)
                except RateLimitException as rle:
                    logger.warning("[LLM] Gemini rate limit detected (Attempt %d): %s", attempt+1, rle)
                    if attempt < retries - 1:
                        wait_time = rle.retry_after + 1.0 if rle.retry_after is not None else delay
                        logger.info("[LLM] Retrying Gemini in %.1f seconds...", wait_time)
                        await asyncio.sleep(wait_time)
                        delay *= 2
                    else:
                        raise rle

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1) -> T | None:
        retries = 5
        delay = 10
        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=temperature,
                    ),
                )
                return schema.model_validate_json(response.text)
            except ValidationError as ve:
                logger.error("Validation error extracting structured data via Gemini: %s", ve)
                return None
            except Exception as e:
                try:
                    self._handle_error(e)
                except RateLimitException as rle:
                    logger.warning("[LLM] Gemini rate limit detected (Attempt %d): %s", attempt+1, rle)
                    if attempt < retries - 1:
                        wait_time = rle.retry_after + 1.0 if rle.retry_after is not None else delay
                        logger.info("[LLM] Retrying Gemini in %.1f seconds...", wait_time)
                        await asyncio.sleep(wait_time)
                        delay *= 2
                    else:
                        logger.error("LLM Structured Extraction failed via Gemini due to rate limit exhaustion.")
                        return None
