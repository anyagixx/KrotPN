"""MTProto owner-safe response schemas.

# FILE: backend/app/mtproto/schemas.py
# VERSION: 1.1.0
# ROLE: TYPES
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Define safe MTProto provisioning and owner dashboard response contracts
#   SCOPE: Owner-facing proxy payload, owner dashboard state, and assignment summary without raw base secret or salt
#   DEPENDS: M-042, M-043, M-045
#   LINKS: M-043, M-045, V-M-043, V-M-045
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoProxyPayload - Owner-safe proxy response including generated tg link
#   MTProtoOwnerProxyStatus - Stable user-cabinet MTProto state values
#   MTProtoOwnerProxyResponse - Owner-only dashboard response with optional secret-bearing fields
#   MTProtoAssignmentSummary - Admin-safe assignment metadata without secrets
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Added Phase-31 owner dashboard proxy response
#   LAST_CHANGE: v1.0.0 - Added Phase-29 MTProto schemas
# END_CHANGE_SUMMARY
"""

from datetime import datetime
from enum import Enum

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


class MTProtoOwnerProxyStatus(str, Enum):
    """Stable MTProto user-cabinet states."""

    ACTIVATED = "activated"
    PENDING = "pending"
    DEGRADED = "degraded"
    UNVERIFIED = "unverified"
    REISSUE_REQUIRED = "reissue_required"


class MTProtoOwnerProxyResponse(BaseModel):
    """Owner-only dashboard response with nullable secret-bearing fields."""

    status: MTProtoOwnerProxyStatus
    safe_message: str
    action_required: str | None = None
    assignment_id: int | None = None
    server: str | None = None
    port: int | None = None
    secret: str | None = None
    tg_link: str | None = None
    sni: str | None = None
    credential_mode: str | None = None
    rotation_marker: str | None = None
    reissue_required: bool = False

    @classmethod
    def from_payload(cls, payload: MTProtoProxyPayload) -> "MTProtoOwnerProxyResponse":
        """Build activated owner response from a secret-bearing payload."""
        return cls(
            status=MTProtoOwnerProxyStatus.ACTIVATED,
            safe_message="MTProto proxy is ready",
            assignment_id=payload.assignment_id,
            server=payload.server,
            port=payload.port,
            secret=payload.secret,
            tg_link=payload.tg_link,
            sni=payload.sni,
            credential_mode=payload.credential_mode,
            rotation_marker=payload.rotation_marker,
            reissue_required=payload.reissue_required,
        )


class MTProtoAssignmentSummary(BaseModel):
    """Admin-safe assignment summary without secret-bearing fields."""

    id: int
    user_id: int
    sni: str
    credential_mode: str
    status: str
    rotation_marker: str
    issued_at: datetime
