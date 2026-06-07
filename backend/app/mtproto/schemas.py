"""MTProto owner-safe response schemas.

# FILE: backend/app/mtproto/schemas.py
# VERSION: 1.2.0
# ROLE: TYPES
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Define safe MTProto provisioning and owner dashboard response contracts
#   SCOPE: Owner-facing proxy payload, owner dashboard state, delivery source metadata,
#          and assignment summary without raw base secret or salt
#   DEPENDS: M-042, M-043, M-045, M-082
#   LINKS: M-043, M-045, M-082, V-M-043, V-M-045, V-M-082
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoProxySource - Owner proxy source discriminator
#   MTProtoProxyPayload - Owner-safe proxy response including generated tg/browser links
#   MTProtoOwnerProxyStatus - Stable user-cabinet MTProto state values
#   MTProtoOwnerProxyResponse - Owner-only dashboard response with optional secret-bearing fields
#   MTProtoAssignmentSummary - Admin-safe assignment metadata without secrets
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Added Phase-80 owner delivery source and external manual telemetry fields.
#   LAST_CHANGE: v1.1.0 - Added Phase-31 owner dashboard proxy response
#   LAST_CHANGE: v1.0.0 - Added Phase-29 MTProto schemas
# END_CHANGE_SUMMARY
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MTProtoProxySource(str, Enum):
    """Stable owner-facing source for the proxy currently being delivered."""

    KROTPN_AUTO = "krotpn_auto"
    MANUAL_EXTERNAL = "manual_external"


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
    browser_link: str | None = None
    source: MTProtoProxySource = MTProtoProxySource.KROTPN_AUTO
    telemetry_available: bool = True
    manual_proxy_name: str | None = None


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
    browser_link: str | None = None
    source: MTProtoProxySource = MTProtoProxySource.KROTPN_AUTO
    telemetry_available: bool = True
    manual_proxy_name: str | None = None

    @classmethod
    def from_payload(cls, payload: MTProtoProxyPayload) -> "MTProtoOwnerProxyResponse":
        """Build activated owner response from a secret-bearing payload."""
        browser_link = payload.browser_link
        if browser_link is None and payload.tg_link.startswith("tg://proxy?"):
            browser_link = payload.tg_link.replace("tg://proxy?", "https://t.me/proxy?", 1)
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
            browser_link=browser_link,
            source=payload.source,
            telemetry_available=payload.telemetry_available,
            manual_proxy_name=payload.manual_proxy_name,
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
