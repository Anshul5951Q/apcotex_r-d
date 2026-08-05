"""
app/dependencies/auth.py

FastAPI dependency injection for authentication and role-based access control.

Usage in routes:
    current_user: User = Depends(get_current_user)
    admin_user:   User = Depends(require_role(UserRole.ADMIN))
"""
import uuid
import logging
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import ForbiddenError, InvalidTokenError

logger = logging.getLogger(__name__)

# Requires "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate the Bearer access token and return the authenticated User.
    Raises HTTP 401 if the token is missing, malformed, expired, or the
    user no longer exists / is inactive.
    """
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise InvalidTokenError()
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise InvalidTokenError()

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)

    if user is None or not user.is_active:
        raise InvalidTokenError()

    return user


def require_role(*roles: UserRole) -> Callable:
    """
    Factory that returns a dependency enforcing one of the given roles.

    Example:
        @router.delete("/users/{id}", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            logger.warning(
                "Role check failed: user %r has role %s, required one of %s",
                current_user.username,
                current_user.role,
                [r.value for r in roles],
            )
            raise ForbiddenError()
        return current_user

    return role_checker
