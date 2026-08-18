"""
app/services/audit_service.py

Centralized audit logging service.
All business services should use this to log audit events.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_actions import AuditAction, AuditEntityType
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Centralized audit logging service."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        detail: Optional[dict] = None,
    ) -> Optional[AuditLog]:
        """
        Log an audit event.

        Args:
            user_id: ID of the user performing the action
            action: Action type (use AuditAction constants)
            entity_type: Type of entity being acted upon (use AuditEntityType constants)
            entity_id: ID of the entity being acted upon
            detail: Additional structured detail about the event

        Returns:
            AuditLog record if successful, None if logging fails
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail or {},
            )
            self._session.add(audit_log)
            await self._session.flush()
            logger.info(
                "Audit logged: user_id=%s action=%s entity_type=%s entity_id=%s",
                user_id,
                action,
                entity_type,
                entity_id,
            )
            return audit_log
        except Exception as e:
            logger.exception("Audit logging failed: user_id=%s action=%s", user_id, action)
            # Do not raise - audit logging failure should not break business operations
            return None
