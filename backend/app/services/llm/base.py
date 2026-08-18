"""
app/services/llm/base.py

Defines the core LLM provider interface.
"""
from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMException(Exception):
    """Base class for all LLM exceptions."""
    def __init__(self, message: str, provider: str = "", model: str = ""):
        super().__init__(message)
        self.provider = provider
        self.model = model

class LLMAuthenticationError(LLMException):
    """Raised for 401 Unauthorized or invalid API keys."""
    pass

class LLMModelUnavailableError(LLMException):
    """Raised for 404 Model Not Found or model no longer available."""
    pass

class LLMRateLimitError(LLMException):
    """Raised for 429 Rate Limit Exceeded (transient)."""
    def __init__(self, message: str, provider: str = "", model: str = "", retry_after: float | None = None, quota_type: str = ""):
        super().__init__(message, provider, model)
        self.retry_after = retry_after
        self.quota_type = quota_type

class LLMQuotaExhaustedError(LLMException):
    """Raised for limit: 0 or absolute quota exhaustion (non-transient)."""
    pass

class LLMProviderUnavailableError(LLMException):
    """Raised when the provider's API is completely unavailable or throws 5xx errors."""
    pass

class LLMInvalidRequestError(LLMException):
    """Raised when the request itself was invalid (400 Bad Request)."""
    pass

class LLMInvalidResponseError(LLMException):
    """Raised when the LLM returns an empty or malformed response that cannot be parsed."""
    pass

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> tuple[str, dict]:
        pass

    @abstractmethod
    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], temperature: float = 0.1) -> tuple[T | None, dict]:
        pass
