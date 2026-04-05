"""Admin audit logging."""

from datetime import datetime, timezone

from loguru import logger
from sqlmodel import Field, SQLModel


class AdminAuditEvent(SQLModel, table=True):
    """Audit event for admin actions."""

    __tablename__ = "admin_audit_events"

    id: int | None = Field(default=None, primary_key=True)
    admin_id: int = Field(index=True)
    action: str = Field(max_length=100)
    resource_type: str | None = Field(default=None, max_length=50)
    resource_id: int | None = Field(default=None)
    details: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


async def log_admin_action(
    session,
    admin_id: int,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: str | None = None,
) -> AdminAuditEvent:
    """Log an admin action to the audit table."""
    event = AdminAuditEvent(
        admin_id=admin_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    session.add(event)
    await session.flush()
    logger.info(
        f"[AUDIT] admin_id={admin_id} action={action} "
        f"resource_type={resource_type} resource_id={resource_id}"
    )
    return event
