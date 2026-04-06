# FILE: backend/app/admin/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Barrel exports for admin module — admin router, audit event model, audit action helper
#   SCOPE: Re-exports public API of the admin module for app-level wiring
#   DEPENDS: M-006 (admin-api router), M-026 (admin-audit-log)
#   LINKS: M-006 (admin-api), M-026 (admin-audit-log)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   admin_router - Admin API router combining admin endpoints and audit
#   AdminAuditEvent - Database model for admin action audit trail
#   log_admin_action - Helper to write audit entries for admin actions
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Admin module exports."""
from app.admin.router import router as admin_router
from app.admin.audit import AdminAuditEvent, log_admin_action

__all__ = [
    "admin_router",
    "AdminAuditEvent",
    "log_admin_action",
]
