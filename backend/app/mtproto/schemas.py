"""MTProto owner-safe response schemas.

# FILE: backend/app/mtproto/schemas.py
# VERSION: 1.0.0
# ROLE: TYPES
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Define safe MTProto provisioning response contracts
#   SCOPE: Owner-facing proxy payload and assignment summary without raw base secret or salt
#   DEPENDS: M-042, M-043
#   LINKS: M-043, V-M-043
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoProxyPayload - Owner-safe proxy response including generated tg link
#   MTProtoAssignmentSummary - Admin-safe assignment metadata without secrets
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-29 MTProto schemas
# END_CHANGE_SUMMARY
"""

from datetime import datetime

from pydantic import BaseModel


class MTProtoProxyPayload(BaseModel):
    """Owner-safe personal MTProto proxy payload."""

    assignment_id: int
    server: str
    port: int
    secret: str
    tg_link: str
    sni: str
    credential_mode: str
    rotation_marker: str
    reissue_required: bool = False


class MTProtoAssignmentSummary(BaseModel):
    """Admin-safe assignment summary without secret-bearing fields."""

    id: int
    user_id: int
    sni: str
    credential_mode: str
    status: str
    rotation_marker: str
    issued_at: datetime
