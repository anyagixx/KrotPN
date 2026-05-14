"""MTProto owner API router.

# FILE: backend/app/mtproto/router.py
# VERSION: 1.0.0
# ROLE: ENTRY_POINT
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Expose authenticated owner-only MTProto proxy state to the user cabinet
#   SCOPE: /api/v1/mtproto/proxy endpoint, owner lookup, provisioning issue/reuse,
#          safe failure mapping, and redacted telemetry
#   DEPENDS: M-001 (core dependencies), M-002 (current user), M-043 (provisioning), M-045
#   LINKS: M-045, V-M-045
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router - FastAPI router for /api/v1/mtproto
#   get_my_mtproto_proxy - Owner-only proxy payload endpoint
#   build_mtproto_service - Testable service factory
#   _safe_failure_response - Stable non-secret failure payload mapper
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-31 owner-only MTProto proxy API
# END_CHANGE_SUMMARY
"""

from loguru import logger
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import CurrentUser, DBSession
from app.mtproto.schemas import MTProtoOwnerProxyResponse, MTProtoOwnerProxyStatus
from app.mtproto.service import (
    MTProtoProvisioningError,
    MTProtoProvisioningErrorCode,
    MTProtoProvisioningService,
)
from app.users.models import User


router = APIRouter(prefix="/api/v1/mtproto", tags=["mtproto"])


# START_CONTRACT: build_mtproto_service
#   PURPOSE: Build MTProto provisioning service for request handling
#   INPUTS: session: AsyncSession
#   OUTPUTS: MTProtoProvisioningService
#   SIDE_EFFECTS: none
#   LINKS: M-045, V-M-045
# END_CONTRACT: build_mtproto_service
# START_BLOCK_SERVICE_FACTORY
def build_mtproto_service(session: AsyncSession) -> MTProtoProvisioningService:
    """Return the provisioning service; tests override this factory."""
    return MTProtoProvisioningService(session)
# END_BLOCK_SERVICE_FACTORY


# START_CONTRACT: get_my_mtproto_proxy
#   PURPOSE: Return current user's owner-only MTProto proxy dashboard payload
#   INPUTS: session: DBSession; current_user: CurrentUser
#   OUTPUTS: MTProtoOwnerProxyResponse
#   SIDE_EFFECTS: creates or reuses restore-safe assignment metadata; never logs secrets
#   LINKS: M-045, M-043, V-M-045
# END_CONTRACT: get_my_mtproto_proxy
# START_BLOCK_GET_MY_MTPROTO_PROXY
@router.get("/proxy", response_model=MTProtoOwnerProxyResponse)
async def get_my_mtproto_proxy(
    session: DBSession,
    current_user: CurrentUser,
) -> MTProtoOwnerProxyResponse:
    """Return the authenticated owner's MTProto proxy state."""
    user_id = int(current_user.id)
    logger.info(f"[M-045][get_my_mtproto_proxy][OWNER_LOOKUP] user_id={user_id}")

    service = build_mtproto_service(session)
    try:
        logger.info(f"[M-045][get_my_mtproto_proxy][ISSUE_OR_REUSE] user_id={user_id}")
        payload = await service.issue_user_proxy(current_user)
    except MTProtoProvisioningError as exc:
        logger.warning(
            "[M-045][get_my_mtproto_proxy][SAFE_FAILURE] "
            f"user_id={user_id} code={exc.code.value}"
        )
        return _safe_failure_response(current_user, exc)

    logger.info(
        "[M-045][get_my_mtproto_proxy][RENDER_PAYLOAD] "
        f"user_id={user_id} assignment_id={payload.assignment_id} status=activated"
    )
    return MTProtoOwnerProxyResponse.from_payload(payload)
# END_BLOCK_GET_MY_MTPROTO_PROXY


# START_CONTRACT: _safe_failure_response
#   PURPOSE: Convert provisioning errors into user-actionable responses without secrets
#   INPUTS: user: User; error: MTProtoProvisioningError
#   OUTPUTS: MTProtoOwnerProxyResponse
#   SIDE_EFFECTS: none
#   LINKS: M-045, V-M-045
# END_CONTRACT: _safe_failure_response
# START_BLOCK_SAFE_FAILURE_RESPONSE
def _safe_failure_response(
    user: User,
    error: MTProtoProvisioningError,
) -> MTProtoOwnerProxyResponse:
    """Map known MTProto failures to stable non-secret dashboard states."""
    if error.code == MTProtoProvisioningErrorCode.USER_NOT_VERIFIED:
        return MTProtoOwnerProxyResponse(
            status=MTProtoOwnerProxyStatus.UNVERIFIED,
            safe_message="Подтвердите email, чтобы получить Telegram proxy.",
            action_required="verify_email",
        )

    if error.code == MTProtoProvisioningErrorCode.REISSUE_REQUIRED:
        return MTProtoOwnerProxyResponse(
            status=MTProtoOwnerProxyStatus.REISSUE_REQUIRED,
            safe_message="Telegram proxy нужно перевыпустить после обновления ключей.",
            action_required="contact_support",
            reissue_required=True,
        )

    if error.code == MTProtoProvisioningErrorCode.CONFIG_INCOMPLETE:
        return MTProtoOwnerProxyResponse(
            status=MTProtoOwnerProxyStatus.PENDING,
            safe_message="Telegram proxy готовится. Попробуйте позже.",
            action_required="wait",
        )

    return MTProtoOwnerProxyResponse(
        status=MTProtoOwnerProxyStatus.DEGRADED,
        safe_message="Telegram proxy временно недоступен. VPN продолжает работать отдельно.",
        action_required="retry_later",
    )
# END_BLOCK_SAFE_FAILURE_RESPONSE
