"""
app/schemas/common.py

Shared response envelopes used across all endpoints.
Every API response is wrapped in SuccessResponse or ErrorResponse
for a consistent client-facing contract.
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard envelope for successful responses."""

    success: bool = True
    data: T


class ErrorDetail(BaseModel):
    """Structured error payload."""

    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Standard envelope for error responses."""

    success: bool = False
    error: ErrorDetail
