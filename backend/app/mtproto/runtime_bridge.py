"""MTProto runtime policy bridge.

# FILE: backend/app/mtproto/runtime_bridge.py
# VERSION: 1.5.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Apply and revoke KrotPN MTProto assignments at a private runtime policy boundary safely
#   SCOPE: Domain policy adapter contract, HTTP live/private-DE adapter, policy apply/revoke, health, replay, telemetry drain, reconciliation, degraded state
#   DEPENDS: M-001 (DB session), M-042 (assignment registry), M-043 (provisioning), M-055 (runtime telemetry)
#   LINKS: M-044, M-055, V-M-044, V-M-055
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoBridgeStatus - Safe runtime bridge status values
#   MTProtoBridgeFailureCode - Safe bridge failure codes
#   MTProtoDomainPolicy - Secret-free policy payload sent to runtime adapter
#   MTProtoPolicyApplyResult - Adapter apply result contract
#   MTProtoRuntimeHealth - Safe health summary contract
#   MTProtoReplayResult - Startup/reconciliation replay summary contract
#   MTProtoPolicyAdapter - Adapter protocol for isolated KPprotoN runtime boundary
#   InMemoryMTProtoPolicyAdapter - Local safe adapter used by tests and offline runtime
#   HTTPMTProtoPolicyAdapter - Token-protected adapter for the live KPprotoN/mtproto_proxy sidecar
#   MTProtoRuntimeTelemetryEvent - Secret-free runtime telemetry event contract
#   MTProtoRuntimeTelemetrySnapshot - Secret-free runtime telemetry snapshot
#   MTProtoRuntimeTelemetryBatch - Drained runtime telemetry batch
#   MTProtoRuntimeBridge - Service for apply, revoke, replay, health, and telemetry operations
#   sync_mtproto_policy - Scheduler-safe reconciliation entry point
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.5.0 - Added Phase-43 runtime resource metric fields to telemetry snapshots.
#   LAST_CHANGE: v1.4.0 - Added Phase-42 runtime telemetry snapshot/drain adapter contract.
#   LAST_CHANGE: v1.3.0 - Mark HTTP adapter operations for Phase-38 private DE runtime tracing.
#   LAST_CHANGE: v1.2.0 - Added Phase-37 HTTP live adapter for the KPprotoN MTProto shared-443 runtime.
#   LAST_CHANGE: v1.1.0 - Added explicit runtime policy revoke path for admin MTProto assignment disable
#   LAST_CHANGE: v1.0.0 - Added Phase-30 safe runtime bridge boundary
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from itertools import islice
from typing import Protocol

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.database import async_session_maker
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus


MAX_REPLAY_ASSIGNMENTS = 1000


# START_BLOCK_RUNTIME_BRIDGE_TYPES
class MTProtoBridgeStatus(str, Enum):
    """Safe runtime bridge states."""

    ACTIVATED = "activated"
    DEGRADED = "degraded"
    HEALTHY = "healthy"
    REVOKED = "revoked"
    SKIPPED = "skipped"


class MTProtoBridgeFailureCode(str, Enum):
    """Stable safe failure codes for bridge operations."""

    ADAPTER_REJECTED = "adapter_rejected"
    BRIDGE_UNAVAILABLE = "bridge_unavailable"
    INVALID_ASSIGNMENT = "invalid_assignment"
    REPLAY_FAILED = "replay_failed"


class MTProtoBridgeUnavailable(RuntimeError):
    """Raised by adapters when the runtime boundary is temporarily unavailable."""


@dataclass(frozen=True)
class MTProtoDomainPolicy:
    """Secret-free domain policy sent to the runtime adapter."""

    assignment_id: int
    user_id: int
    sni: str
    credential_mode: str
    rotation_marker: str


@dataclass(frozen=True)
class MTProtoPolicyApplyResult:
    """Safe result of one policy apply attempt."""

    assignment_id: int | None
    sni: str | None
    status: MTProtoBridgeStatus
    failure_code: MTProtoBridgeFailureCode | None = None
    safe_message: str = ""
    applied_at: datetime | None = None

    def to_safe_dict(self) -> dict[str, object]:
        """Return secret-free result data for tests, health, and admin summaries."""
        return {
            "assignment_id": self.assignment_id,
            "sni": self.sni,
            "status": self.status.value,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "safe_message": self.safe_message,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


@dataclass(frozen=True)
class MTProtoRuntimeHealth:
    """Safe aggregate runtime bridge health state."""

    status: MTProtoBridgeStatus
    adapter_name: str
    last_success_at: datetime | None = None
    last_failure_code: MTProtoBridgeFailureCode | None = None
    last_checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_safe_dict(self) -> dict[str, object]:
        """Return health data without proxy credentials or user-specific secrets."""
        return {
            "status": self.status.value,
            "adapter_name": self.adapter_name,
            "last_success_at": (
                self.last_success_at.isoformat() if self.last_success_at else None
            ),
            "last_failure_code": (
                self.last_failure_code.value if self.last_failure_code else None
            ),
            "last_checked_at": self.last_checked_at.isoformat(),
        }


@dataclass(frozen=True)
class MTProtoReplayResult:
    """Safe summary of startup/reconciliation replay."""

    processed_count: int = 0
    applied_count: int = 0
    skipped_count: int = 0
    degraded_count: int = 0
    failed_count: int = 0

    def to_safe_dict(self) -> dict[str, int]:
        """Return aggregate replay counters only."""
        return {
            "processed_count": self.processed_count,
            "applied_count": self.applied_count,
            "skipped_count": self.skipped_count,
            "degraded_count": self.degraded_count,
            "failed_count": self.failed_count,
        }


@dataclass(frozen=True)
class MTProtoRuntimeTelemetryEvent:
    """Secret-free telemetry event emitted by the MTProto runtime boundary."""

    runtime_event_id: str
    event_type: str
    observed_at: datetime | None = None
    assignment_id: int | None = None
    user_id: int | None = None
    sni: str | None = None
    client_ip: str | None = None
    ip_hash: str | None = None
    ip_prefix: str | None = None
    bytes_in: int = 0
    bytes_out: int = 0
    duration_ms: int = 0
    connection_count: int = 0
    error_code: str | None = None
    reason_code: str | None = None
    metadata: dict[str, object] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "MTProtoRuntimeTelemetryEvent":
        """Build telemetry event from a safe runtime JSON object."""
        observed_raw = payload.get("observed_at")
        observed_at = None
        if isinstance(observed_raw, str) and observed_raw:
            try:
                observed_at = datetime.fromisoformat(observed_raw.replace("Z", "+00:00"))
            except ValueError:
                observed_at = None
        metadata = payload.get("metadata")
        return cls(
            runtime_event_id=str(payload.get("runtime_event_id") or ""),
            event_type=str(payload.get("event_type") or "error"),
            observed_at=observed_at,
            assignment_id=int(payload["assignment_id"]) if payload.get("assignment_id") is not None else None,
            user_id=int(payload["user_id"]) if payload.get("user_id") is not None else None,
            sni=str(payload["sni"]) if payload.get("sni") is not None else None,
            client_ip=str(payload["client_ip"]) if payload.get("client_ip") is not None else None,
            ip_hash=str(payload["ip_hash"]) if payload.get("ip_hash") is not None else None,
            ip_prefix=str(payload["ip_prefix"]) if payload.get("ip_prefix") is not None else None,
            bytes_in=int(payload.get("bytes_in") or 0),
            bytes_out=int(payload.get("bytes_out") or 0),
            duration_ms=int(payload.get("duration_ms") or 0),
            connection_count=int(payload.get("connection_count") or 0),
            error_code=str(payload["error_code"]) if payload.get("error_code") is not None else None,
            reason_code=str(payload["reason_code"]) if payload.get("reason_code") is not None else None,
            metadata=metadata if isinstance(metadata, dict) else None,
        )


@dataclass(frozen=True)
class MTProtoRuntimeTelemetrySnapshot:
    """Secret-free runtime telemetry state."""

    status: MTProtoBridgeStatus
    buffered_events: int = 0
    dropped_events: int = 0
    active_connections: int = 0
    policy_count: int = 0
    last_event_id: str | None = None
    cpu_percent: float | None = None
    memory_rss_bytes: int | None = None
    memory_total_bytes: int | None = None
    memory_processes_bytes: int | None = None
    process_count: int | None = None
    run_queue: int | None = None
    uptime_seconds: int | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_safe_dict(self) -> dict[str, object]:
        resource_values = {
            "cpu_percent": self.cpu_percent,
            "memory_rss_bytes": self.memory_rss_bytes,
            "memory_total_bytes": self.memory_total_bytes,
            "memory_processes_bytes": self.memory_processes_bytes,
            "process_count": self.process_count,
            "run_queue": self.run_queue,
            "uptime_seconds": self.uptime_seconds,
        }
        has_resource_metrics = any(value is not None for value in resource_values.values())
        return {
            "status": self.status.value,
            "buffered_events": self.buffered_events,
            "dropped_events": self.dropped_events,
            "active_connections": self.active_connections,
            "policy_count": self.policy_count,
            "last_event_id": self.last_event_id,
            "resource_metrics": {
                "status": "available" if has_resource_metrics else "unavailable",
                **resource_values,
            },
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass(frozen=True)
class MTProtoRuntimeTelemetryBatch:
    """Runtime telemetry events drained from the private adapter."""

    events: list[MTProtoRuntimeTelemetryEvent]
    next_cursor: int = 0
    dropped_events: int = 0

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "events": [event.runtime_event_id for event in self.events],
            "next_cursor": self.next_cursor,
            "dropped_events": self.dropped_events,
        }


class MTProtoPolicyAdapter(Protocol):
    """Protocol for isolated MTProto runtime policy adapters."""

    adapter_name: str

    async def apply_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        """Apply one secret-free domain policy to runtime state."""

    async def revoke_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        """Remove one secret-free domain policy from runtime state."""

    async def health(self) -> MTProtoRuntimeHealth:
        """Return adapter health without credentials."""

    async def telemetry_snapshot(self) -> MTProtoRuntimeTelemetrySnapshot:
        """Return current telemetry counters without draining events."""

    async def telemetry_drain(
        self,
        *,
        cursor: int = 0,
        limit: int = 500,
    ) -> MTProtoRuntimeTelemetryBatch:
        """Return cursor-ordered telemetry events from the runtime boundary."""
# END_BLOCK_RUNTIME_BRIDGE_TYPES


# START_BLOCK_IN_MEMORY_ADAPTER
class InMemoryMTProtoPolicyAdapter:
    """Local deterministic policy adapter used until a live edge is explicitly wired."""

    adapter_name = "local-memory"

    def __init__(
        self,
        *,
        available: bool = True,
        rejected_snis: set[str] | None = None,
    ) -> None:
        self.available = available
        self.rejected_snis = rejected_snis or set()
        self.policies: dict[str, MTProtoDomainPolicy] = {}
        self.telemetry_events: list[MTProtoRuntimeTelemetryEvent] = []
        self.dropped_events = 0

    async def apply_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        """Apply one policy to local memory, preserving idempotency by SNI."""
        if not self.available:
            raise MTProtoBridgeUnavailable("MTProto runtime bridge is unavailable")
        if policy.sni in self.rejected_snis:
            raise ValueError("MTProto runtime adapter rejected the SNI policy")
        self.policies[policy.sni] = policy

    async def revoke_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        """Remove one local policy by SNI; missing SNI is already revoked."""
        if not self.available:
            raise MTProtoBridgeUnavailable("MTProto runtime bridge is unavailable")
        if policy.sni in self.rejected_snis:
            raise ValueError("MTProto runtime adapter rejected the SNI policy")
        self.policies.pop(policy.sni, None)

    async def health(self) -> MTProtoRuntimeHealth:
        """Return local adapter health state."""
        if not self.available:
            return MTProtoRuntimeHealth(
                status=MTProtoBridgeStatus.DEGRADED,
                adapter_name=self.adapter_name,
                last_failure_code=MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE,
            )
        return MTProtoRuntimeHealth(
            status=MTProtoBridgeStatus.HEALTHY,
            adapter_name=self.adapter_name,
        )

    def emit_telemetry_event(self, event: MTProtoRuntimeTelemetryEvent) -> None:
        """Append one synthetic runtime event for tests and local telemetry smoke."""
        if len(self.telemetry_events) >= 1000:
            self.dropped_events += 1
            logger.warning("[M-055][runtime_telemetry][DROP_OVERFLOW] adapter=local-memory")
            return
        logger.info(
            "[M-055][runtime_telemetry][EMIT_EVENT] "
            f"event_type={event.event_type} assignment_id={event.assignment_id}"
        )
        self.telemetry_events.append(event)

    async def telemetry_snapshot(self) -> MTProtoRuntimeTelemetrySnapshot:
        """Return local telemetry counters without draining events."""
        if not self.available:
            return MTProtoRuntimeTelemetrySnapshot(
                status=MTProtoBridgeStatus.DEGRADED,
                dropped_events=self.dropped_events,
            )
        snapshot = MTProtoRuntimeTelemetrySnapshot(
            status=MTProtoBridgeStatus.HEALTHY,
            buffered_events=len(self.telemetry_events),
            dropped_events=self.dropped_events,
            active_connections=sum(
                max(event.connection_count, 0)
                for event in self.telemetry_events
                if event.event_type == "active_connection"
            ),
            policy_count=len(self.policies),
            last_event_id=self.telemetry_events[-1].runtime_event_id if self.telemetry_events else None,
        )
        logger.info(
            "[M-055][telemetry_snapshot][SNAPSHOT] "
            f"buffered={snapshot.buffered_events} dropped={snapshot.dropped_events}"
        )
        return snapshot

    async def telemetry_drain(
        self,
        *,
        cursor: int = 0,
        limit: int = 500,
    ) -> MTProtoRuntimeTelemetryBatch:
        """Return local telemetry events from a numeric cursor."""
        if not self.available:
            raise MTProtoBridgeUnavailable("MTProto runtime bridge is unavailable")
        safe_cursor = max(cursor, 0)
        safe_limit = min(max(limit, 1), 1000)
        events = list(islice(self.telemetry_events, safe_cursor, safe_cursor + safe_limit))
        next_cursor = safe_cursor + len(events)
        logger.info(
            "[M-055][telemetry_drain][DRAIN_EVENTS] "
            f"cursor={safe_cursor} returned={len(events)} next_cursor={next_cursor}"
        )
        return MTProtoRuntimeTelemetryBatch(
            events=events,
            next_cursor=next_cursor,
            dropped_events=self.dropped_events,
        )
# END_BLOCK_IN_MEMORY_ADAPTER


# START_BLOCK_HTTP_ADAPTER
class HTTPMTProtoPolicyAdapter:
    """Token-protected adapter for the live KPprotoN MTProto edge sidecar."""

    adapter_name = "kpproton-http"

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def apply_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        """Apply one issued SNI to the live MTProto policy table."""
        await self._post_policy("apply", policy)

    async def revoke_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        """Remove one issued SNI from the live MTProto policy table."""
        await self._post_policy("revoke", policy)

    async def health(self) -> MTProtoRuntimeHealth:
        """Return live sidecar health without credentials."""
        try:
            logger.info("[M-044][HTTPMTProtoPolicyAdapter][GET_HEALTH] adapter=kpproton-http")
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self._headers(),
                )
            if response.status_code == 200:
                return MTProtoRuntimeHealth(
                    status=MTProtoBridgeStatus.HEALTHY,
                    adapter_name=self.adapter_name,
                )
            return MTProtoRuntimeHealth(
                status=MTProtoBridgeStatus.DEGRADED,
                adapter_name=self.adapter_name,
                last_failure_code=MTProtoBridgeFailureCode.ADAPTER_REJECTED,
            )
        except httpx.HTTPError:
            return MTProtoRuntimeHealth(
                status=MTProtoBridgeStatus.DEGRADED,
                adapter_name=self.adapter_name,
                last_failure_code=MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE,
            )

    async def telemetry_snapshot(self) -> MTProtoRuntimeTelemetrySnapshot:
        """Return live sidecar telemetry counters without draining events."""
        try:
            logger.info("[M-055][telemetry_snapshot][SNAPSHOT] adapter=kpproton-http")
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/telemetry/snapshot",
                    headers=self._headers(),
                )
            if response.status_code == 200:
                payload = response.json()
                resource_payload = payload.get("resource_metrics") if isinstance(payload.get("resource_metrics"), dict) else {}

                def safe_int(name: str) -> int | None:
                    raw = resource_payload.get(name, payload.get(name))
                    if raw is None:
                        return None
                    try:
                        return max(int(raw), 0)
                    except (TypeError, ValueError):
                        return None

                def safe_float(name: str) -> float | None:
                    raw = resource_payload.get(name, payload.get(name))
                    if raw is None:
                        return None
                    try:
                        return max(float(raw), 0.0)
                    except (TypeError, ValueError):
                        return None

                memory_total = safe_int("memory_total_bytes")
                return MTProtoRuntimeTelemetrySnapshot(
                    status=MTProtoBridgeStatus.HEALTHY,
                    buffered_events=int(payload.get("buffered_events") or 0),
                    dropped_events=int(payload.get("dropped_events") or 0),
                    active_connections=int(payload.get("active_connections") or 0),
                    policy_count=int(payload.get("policy_count") or 0),
                    last_event_id=payload.get("last_event_id"),
                    cpu_percent=safe_float("cpu_percent"),
                    memory_rss_bytes=safe_int("memory_rss_bytes") or memory_total,
                    memory_total_bytes=memory_total,
                    memory_processes_bytes=safe_int("memory_processes_bytes"),
                    process_count=safe_int("process_count"),
                    run_queue=safe_int("run_queue"),
                    uptime_seconds=safe_int("uptime_seconds"),
                )
            return MTProtoRuntimeTelemetrySnapshot(status=MTProtoBridgeStatus.DEGRADED)
        except (httpx.HTTPError, ValueError, TypeError):
            return MTProtoRuntimeTelemetrySnapshot(status=MTProtoBridgeStatus.DEGRADED)

    async def telemetry_drain(
        self,
        *,
        cursor: int = 0,
        limit: int = 500,
    ) -> MTProtoRuntimeTelemetryBatch:
        """Drain live sidecar telemetry through the private token boundary."""
        try:
            logger.info(
                "[M-055][telemetry_drain][DRAIN_EVENTS] "
                f"adapter=kpproton-http cursor={cursor} limit={limit}"
            )
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/telemetry/drain",
                    params={"cursor": max(cursor, 0), "limit": min(max(limit, 1), 1000)},
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise MTProtoBridgeUnavailable("MTProto runtime telemetry bridge is unavailable") from exc

        if response.status_code == 401:
            raise MTProtoBridgeUnavailable("MTProto runtime telemetry bridge rejected credentials")
        if response.status_code >= 400:
            raise ValueError("MTProto runtime telemetry adapter rejected the drain request")
        payload = response.json()
        raw_events = payload.get("events") if isinstance(payload, dict) else []
        events = [
            MTProtoRuntimeTelemetryEvent.from_payload(raw_event)
            for raw_event in raw_events
            if isinstance(raw_event, dict)
        ]
        return MTProtoRuntimeTelemetryBatch(
            events=events,
            next_cursor=int(payload.get("next_cursor") or cursor + len(events)),
            dropped_events=int(payload.get("dropped_events") or 0),
        )

    async def _post_policy(self, operation: str, policy: MTProtoDomainPolicy) -> None:
        payload = {
            "assignment_id": policy.assignment_id,
            "user_id": policy.user_id,
            "sni": policy.sni,
            "credential_mode": policy.credential_mode,
            "rotation_marker": policy.rotation_marker,
        }
        try:
            logger.info(
                "[M-044][HTTPMTProtoPolicyAdapter][POST_APPLY] "
                f"operation={operation} assignment_id={policy.assignment_id} sni={policy.sni}"
            )
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/{operation}",
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise MTProtoBridgeUnavailable("MTProto runtime bridge is unavailable") from exc

        if response.status_code == 401:
            raise MTProtoBridgeUnavailable("MTProto runtime bridge rejected credentials")
        if response.status_code >= 400:
            raise ValueError("MTProto runtime adapter rejected the SNI policy")

    def _headers(self) -> dict[str, str]:
        return {"x-krotpn-mtproto-token": self.token}


def build_default_policy_adapter(app_settings: Settings = settings) -> MTProtoPolicyAdapter:
    """Build the live adapter when configured, otherwise keep local-memory behavior."""
    if app_settings.mtproto_runtime_policy_url and app_settings.mtproto_runtime_token:
        return HTTPMTProtoPolicyAdapter(
            base_url=app_settings.mtproto_runtime_policy_url,
            token=app_settings.mtproto_runtime_token,
            timeout_seconds=app_settings.mtproto_runtime_timeout_seconds,
        )
    return InMemoryMTProtoPolicyAdapter()
# END_BLOCK_HTTP_ADAPTER


default_policy_adapter = build_default_policy_adapter()


class MTProtoRuntimeBridge:
    """Apply and replay KrotPN MTProto assignment policy into runtime state."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        adapter: MTProtoPolicyAdapter | None = None,
    ) -> None:
        self.session = session
        self.adapter = adapter or default_policy_adapter
        self._last_success_at: datetime | None = None
        self._last_failure_code: MTProtoBridgeFailureCode | None = None

    # START_CONTRACT: apply_domain_policy
    #   PURPOSE: Apply one active assignment to the configured runtime adapter
    #   INPUTS: assignment: MTProtoAssignment
    #   OUTPUTS: MTProtoPolicyApplyResult
    #   SIDE_EFFECTS: adapter call and redacted log markers, no DB writes
    #   LINKS: M-044, V-M-044
    # END_CONTRACT: apply_domain_policy
    # START_BLOCK_LOAD_POLICY
    async def apply_domain_policy(
        self,
        assignment: MTProtoAssignment,
    ) -> MTProtoPolicyApplyResult:
        """Apply one assignment without raising runtime outages into caller flows."""
        policy_or_result = self._policy_from_assignment(assignment)
        if isinstance(policy_or_result, MTProtoPolicyApplyResult):
            return policy_or_result

        policy = policy_or_result
        logger.info(
            "[M-044][apply_domain_policy][LOAD_POLICY] "
            f"assignment_id={policy.assignment_id} user_id={policy.user_id} sni={policy.sni}"
        )

        try:
            await self.adapter.apply_domain_policy(policy)
        except MTProtoBridgeUnavailable:
            return self._degraded_result(
                policy,
                failure_code=MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE,
                safe_message="MTProto runtime bridge is unavailable",
            )
        except ValueError:
            return self._degraded_result(
                policy,
                failure_code=MTProtoBridgeFailureCode.ADAPTER_REJECTED,
                safe_message="MTProto runtime adapter rejected the policy",
            )
        except Exception:
            return self._degraded_result(
                policy,
                failure_code=MTProtoBridgeFailureCode.REPLAY_FAILED,
                safe_message="MTProto runtime policy apply failed",
            )

        applied_at = datetime.now(timezone.utc)
        self._last_success_at = applied_at
        self._last_failure_code = None
        logger.info(
            "[M-044][apply_domain_policy][POLICY_APPLIED] "
            f"assignment_id={policy.assignment_id} user_id={policy.user_id} sni={policy.sni}"
        )
        return MTProtoPolicyApplyResult(
            assignment_id=policy.assignment_id,
            sni=policy.sni,
            status=MTProtoBridgeStatus.ACTIVATED,
            applied_at=applied_at,
        )
    # END_BLOCK_LOAD_POLICY

    # START_CONTRACT: revoke_domain_policy
    #   PURPOSE: Remove one assignment SNI from the configured runtime adapter
    #   INPUTS: assignment: MTProtoAssignment
    #   OUTPUTS: MTProtoPolicyApplyResult
    #   SIDE_EFFECTS: adapter call and redacted log markers, no DB writes
    #   LINKS: M-044, M-047, V-M-044, V-M-047
    # END_CONTRACT: revoke_domain_policy
    # START_BLOCK_REVOKE_POLICY
    async def revoke_domain_policy(
        self,
        assignment: MTProtoAssignment,
    ) -> MTProtoPolicyApplyResult:
        """Revoke one assignment policy without raising runtime outages into callers."""
        policy_or_result = self._policy_identity_from_assignment(
            assignment,
            operation="revoke_domain_policy",
            safe_message="MTProto assignment cannot be revoked by runtime bridge",
        )
        if isinstance(policy_or_result, MTProtoPolicyApplyResult):
            return policy_or_result

        policy = policy_or_result
        logger.info(
            "[M-044][revoke_domain_policy][REVOKE_POLICY] "
            f"assignment_id={policy.assignment_id} user_id={policy.user_id} sni={policy.sni}"
        )

        try:
            await self.adapter.revoke_domain_policy(policy)
        except MTProtoBridgeUnavailable:
            return self._degraded_result(
                policy,
                failure_code=MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE,
                safe_message="MTProto runtime bridge is unavailable",
                operation="revoke_domain_policy",
            )
        except ValueError:
            return self._degraded_result(
                policy,
                failure_code=MTProtoBridgeFailureCode.ADAPTER_REJECTED,
                safe_message="MTProto runtime adapter rejected the revoke policy",
                operation="revoke_domain_policy",
            )
        except Exception:
            return self._degraded_result(
                policy,
                failure_code=MTProtoBridgeFailureCode.REPLAY_FAILED,
                safe_message="MTProto runtime policy revoke failed",
                operation="revoke_domain_policy",
            )

        revoked_at = datetime.now(timezone.utc)
        self._last_success_at = revoked_at
        self._last_failure_code = None
        logger.info(
            "[M-044][revoke_domain_policy][POLICY_REVOKED] "
            f"assignment_id={policy.assignment_id} user_id={policy.user_id} sni={policy.sni}"
        )
        return MTProtoPolicyApplyResult(
            assignment_id=policy.assignment_id,
            sni=policy.sni,
            status=MTProtoBridgeStatus.REVOKED,
            applied_at=revoked_at,
        )
    # END_BLOCK_REVOKE_POLICY

    # START_CONTRACT: replay_active_assignments
    #   PURPOSE: Replay assignment registry rows into runtime adapter policy state
    #   INPUTS: limit: int
    #   OUTPUTS: MTProtoReplayResult
    #   SIDE_EFFECTS: adapter calls and aggregate logs, no secret persistence
    #   LINKS: M-044, M-042, V-M-044
    # END_CONTRACT: replay_active_assignments
    # START_BLOCK_REPLAY_POLICY
    async def replay_active_assignments(
        self,
        *,
        limit: int = MAX_REPLAY_ASSIGNMENTS,
    ) -> MTProtoReplayResult:
        """Replay assignment rows idempotently after process or bridge restart."""
        safe_limit = min(max(limit, 1), MAX_REPLAY_ASSIGNMENTS)
        logger.info(
            "[M-044][replay_active_assignments][REPLAY_START] "
            f"limit={safe_limit}"
        )
        result = await self.session.execute(
            select(MTProtoAssignment)
            .order_by(MTProtoAssignment.id.asc())
            .limit(safe_limit)
        )
        assignments = list(result.scalars().all())

        applied_count = 0
        skipped_count = 0
        degraded_count = 0
        failed_count = 0

        for assignment in assignments:
            if assignment.status != MTProtoAssignmentStatus.ACTIVE:
                skipped_count += 1
                continue

            logger.info(
                "[M-044][replay_active_assignments][REPLAY_POLICY] "
                f"assignment_id={assignment.id} user_id={assignment.user_id} sni={assignment.sni}"
            )
            apply_result = await self.apply_domain_policy(assignment)
            if apply_result.status == MTProtoBridgeStatus.ACTIVATED:
                applied_count += 1
            elif apply_result.status == MTProtoBridgeStatus.DEGRADED:
                degraded_count += 1
            else:
                failed_count += 1

        replay_result = MTProtoReplayResult(
            processed_count=len(assignments),
            applied_count=applied_count,
            skipped_count=skipped_count,
            degraded_count=degraded_count,
            failed_count=failed_count,
        )
        logger.info(
            "[M-044][replay_active_assignments][REPLAY_SUMMARY] "
            f"processed={replay_result.processed_count} applied={applied_count} "
            f"skipped={skipped_count} degraded={degraded_count} failed={failed_count}"
        )
        return replay_result
    # END_BLOCK_REPLAY_POLICY

    # START_CONTRACT: runtime_health
    #   PURPOSE: Return aggregate bridge health without exposing proxy credentials
    #   INPUTS: none
    #   OUTPUTS: MTProtoRuntimeHealth
    #   SIDE_EFFECTS: adapter health read and redacted log marker
    #   LINKS: M-044, V-M-044
    # END_CONTRACT: runtime_health
    # START_BLOCK_BRIDGE_HEALTH
    async def runtime_health(self) -> MTProtoRuntimeHealth:
        """Return safe aggregate bridge health."""
        try:
            adapter_health = await self.adapter.health()
        except Exception:
            adapter_health = MTProtoRuntimeHealth(
                status=MTProtoBridgeStatus.DEGRADED,
                adapter_name=getattr(self.adapter, "adapter_name", "unknown"),
                last_success_at=self._last_success_at,
                last_failure_code=MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE,
            )

        if adapter_health.status == MTProtoBridgeStatus.HEALTHY:
            logger.info("[M-044][runtime_health][BRIDGE_HEALTHY] adapter=ok")
            return MTProtoRuntimeHealth(
                status=MTProtoBridgeStatus.HEALTHY,
                adapter_name=adapter_health.adapter_name,
                last_success_at=self._last_success_at or adapter_health.last_success_at,
                last_failure_code=self._last_failure_code,
            )

        logger.warning(
            "[M-044][runtime_health][BRIDGE_DEGRADED] "
            f"failure_code={adapter_health.last_failure_code}"
        )
        return MTProtoRuntimeHealth(
            status=MTProtoBridgeStatus.DEGRADED,
            adapter_name=adapter_health.adapter_name,
            last_success_at=self._last_success_at or adapter_health.last_success_at,
            last_failure_code=adapter_health.last_failure_code or self._last_failure_code,
        )
    # END_BLOCK_BRIDGE_HEALTH

    # START_CONTRACT: telemetry_snapshot
    #   PURPOSE: Return secret-free runtime telemetry and resource counters
    #   INPUTS: none
    #   OUTPUTS: MTProtoRuntimeTelemetrySnapshot
    #   SIDE_EFFECTS: adapter snapshot read and redacted log marker
    #   LINKS: M-055, M-057, V-M-055, V-M-057
    # END_CONTRACT: telemetry_snapshot
    # START_BLOCK_TELEMETRY_SNAPSHOT
    async def telemetry_snapshot(self) -> MTProtoRuntimeTelemetrySnapshot:
        """Return secret-free runtime telemetry and resource metrics."""
        try:
            snapshot = await self.adapter.telemetry_snapshot()
        except Exception:
            snapshot = MTProtoRuntimeTelemetrySnapshot(status=MTProtoBridgeStatus.DEGRADED)
        logger.info(
            "[M-055][telemetry_snapshot][SNAPSHOT] "
            f"status={snapshot.status.value} active={snapshot.active_connections}"
        )
        return snapshot
    # END_BLOCK_TELEMETRY_SNAPSHOT

    # START_BLOCK_RUNTIME_BRIDGE_HELPERS
    def _policy_from_assignment(
        self,
        assignment: MTProtoAssignment,
    ) -> MTProtoDomainPolicy | MTProtoPolicyApplyResult:
        if assignment.status != MTProtoAssignmentStatus.ACTIVE:
            self._last_failure_code = MTProtoBridgeFailureCode.INVALID_ASSIGNMENT
            logger.warning(
                "[M-044][apply_domain_policy][BRIDGE_UNAVAILABLE] "
                "failure_code=invalid_assignment"
            )
            return MTProtoPolicyApplyResult(
                assignment_id=assignment.id,
                sni=assignment.sni,
                status=MTProtoBridgeStatus.SKIPPED,
                failure_code=MTProtoBridgeFailureCode.INVALID_ASSIGNMENT,
                safe_message="MTProto assignment is not active",
            )

        return self._policy_identity_from_assignment(
            assignment,
            operation="apply_domain_policy",
            safe_message="MTProto assignment is not active",
        )

    def _policy_identity_from_assignment(
        self,
        assignment: MTProtoAssignment,
        *,
        operation: str,
        safe_message: str,
    ) -> MTProtoDomainPolicy | MTProtoPolicyApplyResult:
        if assignment.id is None or assignment.user_id is None or not assignment.sni:
            self._last_failure_code = MTProtoBridgeFailureCode.INVALID_ASSIGNMENT
            logger.warning(
                f"[M-044][{operation}][BRIDGE_UNAVAILABLE] "
                "failure_code=invalid_assignment"
            )
            return MTProtoPolicyApplyResult(
                assignment_id=assignment.id,
                sni=assignment.sni,
                status=MTProtoBridgeStatus.SKIPPED,
                failure_code=MTProtoBridgeFailureCode.INVALID_ASSIGNMENT,
                safe_message=safe_message,
            )

        return MTProtoDomainPolicy(
            assignment_id=int(assignment.id),
            user_id=int(assignment.user_id),
            sni=assignment.sni,
            credential_mode=assignment.credential_mode.value,
            rotation_marker=assignment.rotation_marker,
        )

    def _degraded_result(
        self,
        policy: MTProtoDomainPolicy,
        *,
        failure_code: MTProtoBridgeFailureCode,
        safe_message: str,
        operation: str = "apply_domain_policy",
    ) -> MTProtoPolicyApplyResult:
        self._last_failure_code = failure_code
        logger.warning(
            f"[M-044][{operation}][BRIDGE_UNAVAILABLE] "
            f"assignment_id={policy.assignment_id} user_id={policy.user_id} "
            f"sni={policy.sni} failure_code={failure_code.value}"
        )
        return MTProtoPolicyApplyResult(
            assignment_id=policy.assignment_id,
            sni=policy.sni,
            status=MTProtoBridgeStatus.DEGRADED,
            failure_code=failure_code,
            safe_message=safe_message,
        )
    # END_BLOCK_RUNTIME_BRIDGE_HELPERS


# START_CONTRACT: sync_mtproto_policy
#   PURPOSE: Scheduler-safe reconciliation entry point for MTProto runtime policy
#   INPUTS: adapter: MTProtoPolicyAdapter | None
#   OUTPUTS: MTProtoReplayResult
#   SIDE_EFFECTS: local DB read, adapter calls, session commit, redacted logs
#   LINKS: M-044, M-008, V-M-044
# END_CONTRACT: sync_mtproto_policy
# START_BLOCK_SCHEDULER_SYNC
async def sync_mtproto_policy(
    *,
    adapter: MTProtoPolicyAdapter | None = None,
) -> MTProtoReplayResult:
    """Run one scheduler reconciliation cycle without raising bridge outages."""
    logger.info("[M-044][sync_mtproto_policy][SCHEDULER_SYNC] started")
    async with async_session_maker() as session:
        bridge = MTProtoRuntimeBridge(session, adapter=adapter)
        result = await bridge.replay_active_assignments()
        await session.commit()
        logger.info(
            "[M-044][sync_mtproto_policy][SCHEDULER_SYNC] "
            f"processed={result.processed_count} applied={result.applied_count} "
            f"degraded={result.degraded_count}"
        )
        return result
# END_BLOCK_SCHEDULER_SYNC
