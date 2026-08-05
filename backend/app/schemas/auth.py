"""
app/schemas/auth.py

Request / response Pydantic models for authentication endpoints.
"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials submitted to POST /api/v1/auth/login."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Returned on successful login — both access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Body for POST /api/v1/auth/refresh."""

    refresh_token: str = Field(..., min_length=1)


class AccessTokenResponse(BaseModel):
    """Returned after a successful token refresh — new access token only."""

    access_token: str
    token_type: str = "bearer"
