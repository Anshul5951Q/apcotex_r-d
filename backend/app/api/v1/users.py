"""
app/api/v1/users.py

User endpoints:
  GET /api/v1/users/me → current authenticated user profile
"""
from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get(
    "/me",
    response_model=SuccessResponse[UserOut],
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user. Requires Bearer token.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[UserOut]:
    return SuccessResponse(data=UserOut.model_validate(current_user))
