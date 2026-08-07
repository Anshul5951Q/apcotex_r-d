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
        retries = 2
        delay = 2
        for attempt in range(retries + 1):
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
                    logger.warning("[LLM] Gemini rate limit/quota detected: %s", rle)
                    raise rle
                except Exception as ex:
                    # Retry on standard network/API errors
                    if attempt < retries:
                        logger.warning("[LLM] Gemini API error (Attempt %d): %s. Retrying in %.1f sec...", attempt+1, ex, delay)
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        raise ex

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1) -> T | None:
        retries = 2
        delay = 2
        use_response_schema = True
        
        for attempt in range(retries + 1):
            try:
                # If SDK validation failed previously, don't use response_schema
                if use_response_schema:
                    config = genai.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=temperature,
                    )
                    current_prompt = prompt
                else:
                    config = genai.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        temperature=temperature,
                    )
                    schema_json = schema.model_json_schema()
                    current_prompt = prompt + f"\n\nReturn ONLY a JSON object that strictly matches this schema:\n{schema_json}"

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=current_prompt,
                    config=config,
                )
                return schema.model_validate_json(response.text)
                
            except ValidationError as ve:
                if use_response_schema:
                    logger.warning("Gemini SDK schema validation error (likely $defs). Disabling response_schema and retrying...: %s", ve)
                    use_response_schema = False
                    continue # Try again immediately in the next loop iteration without sleeping
                else:
                    logger.error("Validation error extracting structured data via Gemini even with manual schema: %s", ve)
                    return None
                    
            except Exception as e:
                try:
                    self._handle_error(e)
                except RateLimitException as rle:
                    logger.warning("[LLM] Gemini rate limit/quota detected: %s", rle)
                    raise rle
                except Exception as ex:
                    if attempt < retries:
                        logger.warning("[LLM] Gemini API error (Attempt %d): %s. Retrying in %.1f sec...", attempt+1, ex, delay)
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        logger.error("LLM Structured Extraction failed via Gemini due to persistent errors.")
                        return None
