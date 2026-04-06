# FILE: backend/app/admin/audit.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Admin action audit trail — persist and query admin API request logs
#   SCOPE: AdminAuditEvent model, middleware for logging admin requests, query helpers
#   DEPENDS: M-001 (core database), M-006 (admin-api)
#   LINKS: M-026 (admin-audit-log), V-M-026
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AdminAuditEvent - Persisted audit record with admin_id, action, resource_type, details
#   AdminAuditMiddleware - FastAPI middleware logging all /api/v1/admin/* requests
#   log_admin_action - Helper to write audit entries
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, BLOCKS per GRACE governance protocol
# END_CHANGE_SUMMARY
#

"""Admin audit logging."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


# START_BLOCK: log_admin_action
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
# END_BLOCK: log_admin_action
