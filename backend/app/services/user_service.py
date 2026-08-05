"""
app/services/user_service.py

Business logic for user-related operations.
Phase 2 will add create_user(), list_users(), update_role(), etc.
"""
import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class UserService:
    """Handles user retrieval and management business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        """
        Return a User by UUID.
        Raises NotFoundError if the user does not exist.
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(resource="User")
        return user

    async def get_by_email(self, email: str) -> User:
        """
        Return a User by email address.
        Raises NotFoundError if the user does not exist.
        """
        user = await self._repo.get_by_email(email)
        if user is None:
            raise NotFoundError(resource="User")
        return user
