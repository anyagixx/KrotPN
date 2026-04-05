# START_MODULE_CONTRACT: M-026
# PURPOSE: Admin audit logging model and middleware for /api/v1/admin/* requests
# SCOPE: AdminAuditEvent SQLModel, log_admin_action helper, AdminAuditMiddleware
# INPUTS: Admin user ID from JWT, request path/method, resource details
# OUTPUTS: Persisted audit records in admin_audit_events table, structured log entries
# DEPENDENCIES: M-001 (core DB settings), M-006 (admin-api)
# VERIFICATION: V-M-026 — every admin request produces audit record
# END_MODULE_CONTRACT: M-026
# START_MODULE_CONTRACT: M-026
# PURPOSE: Admin audit logging model and middleware for /api/v1/admin/* requests
# SCOPE: AdminAuditEvent SQLModel, log_admin_action helper, AdminAuditMiddleware
# INPUTS: Admin user ID from JWT, request path/method, resource details
# OUTPUTS: Persisted audit records in admin_audit_events table, structured log entries
# DEPENDENCIES: M-001 (core DB settings), M-006 (admin-api)
# VERIFICATION: V-M-026 — every admin request produces audit record
# END_MODULE_CONTRACT: M-026
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
