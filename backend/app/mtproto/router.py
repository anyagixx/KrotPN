"""MTProto owner API router.

# FILE: backend/app/mtproto/router.py
# VERSION: 1.2.0
# ROLE: ENTRY_POINT
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Expose authenticated owner-only MTProto proxy state and private router telemetry ingestion
#   SCOPE: /api/v1/mtproto/proxy endpoint, owner lookup, delivery-mode selection,
#          provisioning issue/reuse, safe failure mapping, and redacted telemetry
#   DEPENDS: M-001 (core dependencies), M-002 (current user), M-043 (provisioning), M-045, M-055, M-061, M-082
#   LINKS: M-045, M-055, M-061, M-082, V-M-045, V-M-055, V-M-061, V-M-082
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router - FastAPI router for /api/v1/mtproto
#   get_my_mtproto_proxy - Owner-only proxy payload endpoint
#   ingest_router_observations - Token-protected RU SNI-router client-IP telemetry endpoint
#   build_mtproto_service - Testable service factory
#   build_mtproto_manual_proxy_pool - Testable manual external delivery service factory
#   _safe_failure_response - Stable non-secret failure payload mapper
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Added Phase-80 manual external delivery selector before automatic provisioning.
#   LAST_CHANGE: v1.1.0 - Added token-protected RU SNI-router real client IP observation ingestion.
#   LAST_CHANGE: v1.0.0 - Added Phase-31 owner-only MTProto proxy API
# END_CHANGE_SUMMARY
"""

from datetime import datetime
from hmac import compare_digest

from loguru import logger
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import CurrentUser, DBSession
from app.core.config import settings
from app.mtproto.schemas import MTProtoOwnerProxyResponse, MTProtoOwnerProxyStatus
from app.mtproto.service import (
    MTProtoManualProxyPoolService,
    MTProtoProvisioningError,
    MTProtoProvisioningErrorCode,
    MTProtoProvisioningService,
)
from app.mtproto.usage_repository import MTProtoTelemetryEvent, ingest_telemetry_batch
from app.users.models import User


router = APIRouter(prefix="/api/v1/mtproto", tags=["mtproto"])


# START_BLOCK_ROUTER_OBSERVATION_SCHEMAS
class MTProtoRouterObservation(BaseModel):
    """One trusted RU SNI-router observation for a real client device IP."""

    runtime_event_id: str = Field(min_length=8, max_length=128)
    observed_at: datetime | None = None
    sni: str = Field(min_length=3, max_length=255)
    client_ip: str = Field(min_length=3, max_length=64)
    connection_count: int = Field(default=1, ge=1, le=1000)
    reason_code: str = Field(default="ru_sni_router_client_ip", max_length=80)


class MTProtoRouterObservationBatch(BaseModel):
    """Batch posted by the local RU router telemetry collector."""

    events: list[MTProtoRouterObservation] = Field(default_factory=list, max_length=500)
# END_BLOCK_ROUTER_OBSERVATION_SCHEMAS


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


# START_CONTRACT: build_mtproto_manual_proxy_pool
#   PURPOSE: Build manual external proxy delivery service for request handling
#   INPUTS: session: AsyncSession
#   OUTPUTS: MTProtoManualProxyPoolService
#   SIDE_EFFECTS: none
#   LINKS: M-082, V-M-082
# END_CONTRACT: build_mtproto_manual_proxy_pool
# START_BLOCK_MANUAL_SERVICE_FACTORY
def build_mtproto_manual_proxy_pool(session: AsyncSession) -> MTProtoManualProxyPoolService:
    """Return the manual proxy pool service; tests override this factory if needed."""
    return MTProtoManualProxyPoolService(session)
# END_BLOCK_MANUAL_SERVICE_FACTORY


# START_CONTRACT: ingest_router_observations
#   PURPOSE: Persist real client IP observations captured at the RU SNI-router boundary
#   INPUTS: session: DBSession; payload: MTProtoRouterObservationBatch; x-krotpn-mtproto-token header
#   OUTPUTS: safe ingestion counters
#   SIDE_EFFECTS: writes M-054 telemetry rows and M-061 encrypted IP observations
#   LINKS: M-055, M-061, V-M-055, V-M-061
# END_CONTRACT: ingest_router_observations
# START_BLOCK_ROUTER_OBSERVATION_INGEST
@router.post("/router-observations")
async def ingest_router_observations(
    session: DBSession,
    payload: MTProtoRouterObservationBatch,
    runtime_token: str | None = Header(default=None, alias="x-krotpn-mtproto-token"),
) -> dict[str, object]:
    """Ingest real user-device IPs observed before RU-to-DE proxying."""
    expected_token = settings.mtproto_runtime_token
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MTProto runtime token is disabled")
    if not runtime_token or not compare_digest(runtime_token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MTProto runtime token")

    result = await ingest_telemetry_batch(
        session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id=event.runtime_event_id,
                event_type="ip_observation",
                observed_at=event.observed_at,
                sni=event.sni.strip().lower(),
                client_ip=event.client_ip,
                connection_count=event.connection_count,
                reason_code=event.reason_code,
                metadata={"source": "ru_sni_router"},
            )
            for event in payload.events
        ],
    )
    logger.info(
        "[M-055][router_observation_ingest][INGEST_SUMMARY] "
        f"received={result.received_count} written={result.written_count} skipped={result.skipped_count}"
    )
    return {
        "status": "ok",
        "received_count": result.received_count,
        "written_count": result.written_count,
        "skipped_count": result.skipped_count,
    }
# END_BLOCK_ROUTER_OBSERVATION_INGEST


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

    manual_pool = build_mtproto_manual_proxy_pool(session)
    manual_response = await manual_pool.owner_response_for_current_mode(current_user)
    if manual_response is not None:
        logger.info(
            "[M-082][get_my_mtproto_proxy][DELIVERY_MODE] "
            f"user_id={user_id} source={manual_response.source.value} status={manual_response.status.value}"
        )
        return manual_response

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
