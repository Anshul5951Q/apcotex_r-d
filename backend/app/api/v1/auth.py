"""
app/api/v1/auth.py

Authentication endpoints:
  POST /api/v1/auth/login    → returns access + refresh token
  POST /api/v1/auth/refresh  → returns new access token
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    summary="Login with username and password",
    description=(
        "Authenticate with username + password. "
        "Returns a short-lived access token and a long-lived refresh token."
    ),
)
async def login(
    credentials: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[TokenResponse]:
    service = AuthService(session)
    tokens = await service.login(credentials)
    return SuccessResponse(data=tokens)


@router.post(
    "/refresh",
    response_model=SuccessResponse[AccessTokenResponse],
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new short-lived access token.",
)
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[AccessTokenResponse]:
    service = AuthService(session)
    token = await service.refresh(body.refresh_token)
    return SuccessResponse(data=token)
