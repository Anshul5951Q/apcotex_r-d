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
from app.services.llm.base import (
    BaseLLMProvider, T, 
    LLMAuthenticationError, LLMModelUnavailableError,
    LLMRateLimitError, LLMQuotaExhaustedError, 
    LLMProviderUnavailableError, LLMInvalidRequestError,
    LLMInvalidResponseError
)
from app.services.pipeline.schemas import PatentExtraction

logger = logging.getLogger(__name__)

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY

        if self.api_key:
            self.api_key = self.api_key.strip()
        else:
            logger.error("GEMINI_API_KEY_PRESENT: NO")
            raise ValueError("Gemini API key is not configured.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = getattr(settings, 'GEMINI_MODEL', None) or "gemini-2.5-flash"
        logger.info("[Gemini] Initialized | model=%s", self.model_name)

    def _classify_quota_error(self, e_str: str) -> tuple[str, float | None]:
        retry_after = None
        match = re.search(r'retry in ([\d\.]+)s', e_str, re.IGNORECASE)
        if match:
            try:
                retry_after = float(match.group(1))
            except ValueError:
                pass
                
        classification = "UNKNOWN_429"
        if "limit: 0" in e_str or "ZERO_QUOTA" in e_str:
            classification = "ZERO_QUOTA"
        elif "GenerateRequestsPerDay" in e_str:
            classification = "RPD_EXCEEDED"
        elif "GenerateRequestsPerMinute" in e_str:
            classification = "RPM_EXCEEDED"
        elif "InputTokensPerModelPerMinute" in e_str or "TokensPer" in e_str:
            classification = "TPM_EXCEEDED"
        
        return classification, retry_after

    def _handle_error(self, e: Exception):
        if isinstance(e, APIError):
            code = getattr(e, 'code', None)
            e_str = str(e)

            # Explicitly handle API_KEY_INVALID - do not mask as rate limit or other error
            if "API_KEY_INVALID" in e_str or "API key not valid" in e_str:
                logger.error("GEMINI_AUTHENTICATION_FAILED: API_KEY_INVALID")
                raise LLMAuthenticationError(f"Gemini Authentication Failed (API_KEY_INVALID): {e_str}", provider="gemini", model=self.model_name) from e

            if code in (401, 403):
                raise LLMAuthenticationError(f"Gemini Authentication/Permission Error: {e_str}", provider="gemini", model=self.model_name) from e
            elif code == 404 or "model no longer available" in e_str.lower() or "not found" in e_str.lower():
                raise LLMModelUnavailableError(f"Gemini Model Unavailable: {e_str}", provider="gemini", model=self.model_name) from e
            elif code == 400:
                raise LLMInvalidRequestError(f"Gemini Invalid Request: {e_str}", provider="gemini", model=self.model_name) from e
            elif code == 503 or "503" in e_str:
                raise LLMRateLimitError(
                    f"Gemini Service Unavailable (503): {e_str}",
                    provider="gemini",
                    model=self.model_name,
                    retry_after=2.0,
                    quota_type="TEMPORARY_PROVIDER_FAILURE"
                ) from e
            elif code is not None and code >= 500:
                raise LLMProviderUnavailableError(f"Gemini Server Error: {e_str}", provider="gemini", model=self.model_name) from e
            elif code == 429 or "Quota exceeded" in e_str:
                classification, retry_after = self._classify_quota_error(e_str)
                if classification in ["ZERO_QUOTA", "RPD_EXCEEDED"]:
                    raise LLMQuotaExhaustedError(f"Gemini Quota Exhausted ({classification}): {e_str}", provider="gemini", model=self.model_name) from e
                else:
                    raise LLMRateLimitError(
                        f"Gemini Rate Limit ({classification}): {e_str}",
                        provider="gemini",
                        model=self.model_name,
                        retry_after=retry_after,
                        quota_type=classification
                    ) from e

        raise e

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> tuple[str, dict]:
        try:
            logger.info("[LLM] Gemini request model: %s", self.model_name)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                ),
            )
            
            usage = {}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = {
                    "input_tokens": getattr(response.usage_metadata, "prompt_token_count", None),
                    "output_tokens": getattr(response.usage_metadata, "candidates_token_count", None),
                }
                
            return response.text, usage
        except Exception as e:
            self._handle_error(e)

    def _validate_gemini_schema(self, schema: dict, path: str = "root") -> list[str]:
        """
        Recursively validate that all required fields exist in properties.
        Returns list of validation errors.
        """
        errors = []
        
        if not isinstance(schema, dict):
            return errors
            
        # Check if this is an object with properties and required
        if "properties" in schema:
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            # Check each required field exists in properties
            for req_field in required:
                if req_field not in properties:
                    errors.append(f"Path: {path} | Required field '{req_field}' not found in properties")
            
            # Recursively validate nested objects in properties
            for prop_name, prop_schema in properties.items():
                nested_path = f"{path}.{prop_name}"
                if isinstance(prop_schema, dict):
                    # Handle array items
                    if "items" in prop_schema and isinstance(prop_schema["items"], dict):
                        errors.extend(self._validate_gemini_schema(prop_schema["items"], f"{nested_path}.items"))
                    # Handle nested objects
                    else:
                        errors.extend(self._validate_gemini_schema(prop_schema, nested_path))
                elif isinstance(prop_schema, list):
                    for idx, item in enumerate(prop_schema):
                        if isinstance(item, dict):
                            errors.extend(self._validate_gemini_schema(item, f"{nested_path}[{idx}]"))
        
        return errors

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1) -> tuple[T | None, dict]:
        try:
            from app.services.llm.schema_normalizer import normalize_gemini_schema

            raw_schema = schema.model_json_schema()
            response_schema_dict = normalize_gemini_schema(raw_schema)

            # Validate schema recursively (log errors only)
            validation_errors = self._validate_gemini_schema(response_schema_dict)
            if validation_errors:
                logger.error("[Gemini] Schema validation errors for %s:", schema.__name__)
                for error in validation_errors:
                    logger.error("  %s", error)

            config = genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=response_schema_dict,
                temperature=temperature,
            )

            logger.info("[LLM] Gemini request model: %s", self.model_name)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            # Check for EMPTY_RESPONSE before parsing
            if response.text is None:
                logger.error("GEMINI_RESPONSE_ERROR: EMPTY_RESPONSE")
                raise LLMInvalidResponseError("EMPTY_RESPONSE", provider="gemini", model=self.model_name)

            # Log diagnostic information about the raw response
            logger.info("GEMINI_STRUCTURED_RESPONSE_RECEIVED: YES")
            logger.info("GEMINI_RESPONSE_TYPE: %s", type(response.text))
            logger.info("GEMINI_RESPONSE_LENGTH: %d", len(response.text))

            # Try to parse as JSON to get keys
            try:
                import json
                response_dict = json.loads(response.text)
                logger.info("GEMINI_RESPONSE_KEYS: %s", list(response_dict.keys()))
                # Log a sanitized preview (first 200 chars)
                preview = response.text[:200] if len(response.text) > 200 else response.text
                logger.info("GEMINI_RESPONSE_PREVIEW: %s", preview)
            except json.JSONDecodeError as jde:
                logger.warning("GEMINI_RESPONSE_NOT_VALID_JSON")
                raise LLMInvalidResponseError(f"MALFORMED_JSON: {jde}", provider="gemini", model=self.model_name)

            usage = {}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = {
                    "input_tokens": getattr(response.usage_metadata, "prompt_token_count", None),
                    "output_tokens": getattr(response.usage_metadata, "candidates_token_count", None),
                }
                
            return schema.model_validate_json(response.text), usage

        except ValidationError as ve:
            logger.error("LLM Schema Mode: FAILED. Validation error extracting structured data via Gemini: %s", ve)
            logger.error("Missing or invalid fields in Gemini response. The LLM did not return the expected schema.")
            # Capture whatever usage we can before failing so telemetry records the cost
            _failed_usage = {}
            try:
                if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
                    _failed_usage = {
                        "input_tokens": getattr(response.usage_metadata, "prompt_token_count", None),
                        "output_tokens": getattr(response.usage_metadata, "candidates_token_count", None),
                    }
                elif response and hasattr(response, 'text') and response.text:
                    # Estimate output from response length
                    _failed_usage = {"output_tokens": len(response.text) // 4}
            except Exception:
                pass
            # Re-raise as a structured validation error so llm_client records status=validation_failed
            from pydantic import ValidationError as VE
            raise VE.from_exception_data(ve.title, ve.errors(), ve.error_count()) if False else ve  # passthrough
        except Exception as e:
            self._handle_error(e)

