# FILE: backend/app/vpn/anti_abuse.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Anti-ping-pong abuse detection for device-bound AWG peers
#   SCOPE: Endpoint IP normalization, short-lived history storage, roaming/ping-pong classification, soft auto-rotation enforcement
#   DEPENDS: M-001 (settings/Redis), M-003 (VPN provisioning), M-020 (device registry), M-021 (device policy), M-025 (audit log)
#   LINKS: M-031 (anti-ping-pong-abuse), V-M-031
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AntiAbuseMode - Runtime mode: disabled, observe, auto_rotate
#   AntiAbuseDecisionKind - Classifier decision enum
#   AntiAbuseConfig - Runtime thresholds resolved from settings
#   EndpointHistoryEntry - One normalized endpoint-IP observation in history
#   EndpointObservation - Current peer observation produced from AWG stats
#   AntiAbuseDecision - Classifier result with safe audit context
#   InMemoryEndpointHistoryStore - Deterministic test store
#   RedisEndpointHistoryStore - TTL Redis store for production endpoint history and cooldown locks
#   normalize_endpoint_ip - Extract stable endpoint IP while ignoring NAT port changes
#   classify_endpoint_history - Detect ping-pong and multi-network abuse from bounded history
#   AntiAbuseAnalyzer - Records observations and returns classifier decisions
#   AntiAbuseEnforcer - Applies soft auto-rotation with cooldown
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.1.0 - Added Redis-backed anti-ping-pong classifier and soft auto-rotation enforcement
# END_CHANGE_SUMMARY
#
"""Anti-ping-pong abuse detection for AWG endpoint churn."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import ipaddress
import json
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.devices.models import (
    DeviceEventSeverity,
    DeviceSecurityEvent,
    DeviceSecurityEventType,
    UserDevice,
)
from app.devices.service import DeviceAccessPolicyService
from app.vpn.models import VPNClient
from app.vpn.service import VPNService


# START_BLOCK: AntiAbuseMode
class AntiAbuseMode(str, Enum):
    """Runtime mode for anti-abuse decisions."""

    DISABLED = "disabled"
    OBSERVE = "observe"
    AUTO_ROTATE = "auto_rotate"
# END_BLOCK: AntiAbuseMode


# START_BLOCK: AntiAbuseDecisionKind
class AntiAbuseDecisionKind(str, Enum):
    """Stable classifier results."""

    DISABLED = "disabled"
    OK = "ok"
    ROAMING = "roaming"
    WARNING = "warning"
    PING_PONG_ABUSE = "ping_pong_abuse"
    MULTI_NETWORK_ABUSE = "multi_network_abuse"
    DEGRADED = "degraded"
# END_BLOCK: AntiAbuseDecisionKind


class AntiAbuseStoreUnavailable(RuntimeError):
    """Raised when endpoint history storage cannot be reached safely."""


# START_BLOCK: AntiAbuseConfig
@dataclass(frozen=True)
class AntiAbuseConfig:
    """Runtime thresholds for anti-abuse classification and enforcement."""

    mode: AntiAbuseMode = AntiAbuseMode.OBSERVE
    history_window_seconds: int = 300
    history_ttl_seconds: int = 900
    pingpong_window_seconds: int = 180
    pingpong_min_alternations: int = 4
    unique_ip_threshold: int = 4
    enforcement_cooldown_seconds: int = 900

    @classmethod
    def from_settings(cls) -> "AntiAbuseConfig":
        """Build config from application settings."""
        return cls(
            mode=AntiAbuseMode(settings.anti_abuse_mode),
            history_window_seconds=settings.anti_abuse_history_window_seconds,
            history_ttl_seconds=settings.anti_abuse_history_ttl_seconds,
            pingpong_window_seconds=settings.anti_abuse_pingpong_window_seconds,
            pingpong_min_alternations=settings.anti_abuse_pingpong_min_alternations,
            unique_ip_threshold=settings.anti_abuse_unique_ip_threshold,
            enforcement_cooldown_seconds=settings.anti_abuse_enforcement_cooldown_seconds,
        )
# END_BLOCK: AntiAbuseConfig


# START_BLOCK: EndpointHistoryEntry
@dataclass(frozen=True)
class EndpointHistoryEntry:
    """One normalized endpoint IP observation."""

    ip: str
    observed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize entry for Redis JSON storage."""
        return {"ip": self.ip, "observed_at": self.observed_at.isoformat()}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EndpointHistoryEntry":
        """Deserialize entry from Redis JSON storage."""
        observed_at = datetime.fromisoformat(str(payload["observed_at"]))
        return cls(ip=str(payload["ip"]), observed_at=_coerce_datetime(observed_at))
# END_BLOCK: EndpointHistoryEntry


# START_BLOCK: EndpointObservation
@dataclass(frozen=True)
class EndpointObservation:
    """Current endpoint observation for one device-bound peer."""

    peer_hash: str
    user_id: int
    device_id: int
    ip: str | None
    endpoint: str | None
    observed_at: datetime

    @classmethod
    def from_peer(
        cls,
        *,
        public_key: str,
        user_id: int,
        device_id: int,
        endpoint: str | None,
        observed_at: datetime,
    ) -> "EndpointObservation":
        """Create an observation while hashing the peer key for safe storage/logging."""
        return cls(
            peer_hash=hash_peer_public_key(public_key),
            user_id=user_id,
            device_id=device_id,
            ip=normalize_endpoint_ip(endpoint),
            endpoint=endpoint,
            observed_at=_coerce_datetime(observed_at),
        )
# END_BLOCK: EndpointObservation


# START_BLOCK: AntiAbuseDecision
@dataclass(frozen=True)
class AntiAbuseDecision:
    """Classifier decision with safe context for logs and audit events."""

    kind: AntiAbuseDecisionKind
    reason: str
    peer_hash: str
    user_id: int
    device_id: int
    ip: str | None = None
    history_ips: tuple[str, ...] = ()
    event_type: DeviceSecurityEventType | None = None
    should_enforce: bool = False

    def details_json(self) -> str:
        """Return safe JSON context for durable audit events."""
        return json.dumps(
            {
                "reason": self.reason,
                "peer_hash": self.peer_hash,
                "ip": self.ip,
                "history_ips": list(self.history_ips),
                "decision": self.kind.value,
            },
            separators=(",", ":"),
        )
# END_BLOCK: AntiAbuseDecision


# START_BLOCK: InMemoryEndpointHistoryStore
class InMemoryEndpointHistoryStore:
    """Deterministic endpoint history store for tests."""

    def __init__(self) -> None:
        self.histories: dict[str, list[EndpointHistoryEntry]] = {}
        self.cooldowns: dict[str, datetime] = {}

    async def load_history(self, peer_hash: str) -> list[EndpointHistoryEntry]:
        """Load current history entries."""
        return list(self.histories.get(peer_hash, []))

    async def save_history(
        self,
        peer_hash: str,
        history: list[EndpointHistoryEntry],
        ttl_seconds: int,
    ) -> None:
        """Persist history entries."""
        self.histories[peer_hash] = list(history)

    async def acquire_cooldown_lock(self, device_id: int, ttl_seconds: int) -> bool:
        """Acquire a per-device cooldown lock."""
        key = str(device_id)
        now = datetime.now(timezone.utc)
        expires_at = self.cooldowns.get(key)
        if expires_at is not None and expires_at > now:
            return False
        self.cooldowns[key] = now + timedelta(seconds=ttl_seconds)
        return True
# END_BLOCK: InMemoryEndpointHistoryStore


# START_BLOCK: RedisEndpointHistoryStore
class RedisEndpointHistoryStore:
    """Redis-backed endpoint history and cooldown store."""

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or settings.redis_url
        self._client: Any = None

    def _redis(self) -> Any:
        """Create Redis client lazily so tests can import without Redis."""
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
            except Exception as exc:  # pragma: no cover - import failure is env-specific
                raise AntiAbuseStoreUnavailable(str(exc)) from exc
        return self._client

    async def load_history(self, peer_hash: str) -> list[EndpointHistoryEntry]:
        """Load peer history from Redis."""
        try:
            raw = await self._redis().get(_history_key(peer_hash))
            if not raw:
                return []
            payload = json.loads(raw)
            return [EndpointHistoryEntry.from_dict(item) for item in payload]
        except Exception as exc:
            raise AntiAbuseStoreUnavailable(str(exc)) from exc

    async def save_history(
        self,
        peer_hash: str,
        history: list[EndpointHistoryEntry],
        ttl_seconds: int,
    ) -> None:
        """Save peer history to Redis with TTL."""
        try:
            payload = json.dumps([entry.to_dict() for entry in history], separators=(",", ":"))
            await self._redis().setex(_history_key(peer_hash), ttl_seconds, payload)
        except Exception as exc:
            raise AntiAbuseStoreUnavailable(str(exc)) from exc

    async def acquire_cooldown_lock(self, device_id: int, ttl_seconds: int) -> bool:
        """Acquire a Redis NX cooldown lock for one device."""
        try:
            result = await self._redis().set(
                _cooldown_key(device_id),
                "1",
                ex=ttl_seconds,
                nx=True,
            )
            return bool(result)
        except Exception as exc:
            raise AntiAbuseStoreUnavailable(str(exc)) from exc
# END_BLOCK: RedisEndpointHistoryStore


# START_BLOCK: normalize_endpoint_ip
def normalize_endpoint_ip(endpoint: str | None) -> str | None:
    """Extract a stable endpoint IP and ignore NAT port-only changes."""
    if not endpoint:
        return None

    value = endpoint.strip()
    if not value or value.lower() == "none":
        return None

    host = value
    if value.startswith("["):
        closing = value.find("]")
        if closing > 1:
            host = value[1:closing]
    else:
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            if value.count(":") == 1:
                host = value.rsplit(":", 1)[0]
            elif ":" in value:
                return None

    host = host.strip()
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return host.lower() or None
# END_BLOCK: normalize_endpoint_ip


# START_BLOCK: classify_endpoint_history
def classify_endpoint_history(
    history: list[EndpointHistoryEntry],
    *,
    now: datetime,
    config: AntiAbuseConfig,
) -> AntiAbuseDecisionKind:
    """Classify bounded endpoint history as roaming, warning or abuse."""
    recent = _recent_history(
        history,
        now=now,
        window_seconds=config.history_window_seconds,
    )
    pingpong_recent = _recent_history(
        history,
        now=now,
        window_seconds=config.pingpong_window_seconds,
    )
    ips = [entry.ip for entry in recent]
    pingpong_ips = [entry.ip for entry in pingpong_recent]
    unique_ips = set(ips)

    if len(unique_ips) <= 1:
        return AntiAbuseDecisionKind.OK
    if _has_ping_pong_pattern(
        pingpong_ips,
        min_alternations=config.pingpong_min_alternations,
    ):
        return AntiAbuseDecisionKind.PING_PONG_ABUSE
    if len(unique_ips) >= config.unique_ip_threshold:
        return AntiAbuseDecisionKind.MULTI_NETWORK_ABUSE
    if len(unique_ips) == 2:
        return AntiAbuseDecisionKind.ROAMING
    return AntiAbuseDecisionKind.WARNING
# END_BLOCK: classify_endpoint_history


# START_BLOCK: AntiAbuseAnalyzer
class AntiAbuseAnalyzer:
    """Record endpoint history and classify current peer behavior."""

    def __init__(
        self,
        *,
        store: InMemoryEndpointHistoryStore | RedisEndpointHistoryStore | None = None,
        config: AntiAbuseConfig | None = None,
    ) -> None:
        self.config = config or AntiAbuseConfig.from_settings()
        self.store = store or RedisEndpointHistoryStore()

    async def analyze(self, observation: EndpointObservation) -> AntiAbuseDecision:
        """Record observation and return an anti-abuse decision."""
        if self.config.mode is AntiAbuseMode.DISABLED:
            return self._decision(observation, AntiAbuseDecisionKind.DISABLED, "disabled")

        if observation.ip is None:
            return self._decision(observation, AntiAbuseDecisionKind.OK, "missing_endpoint_ip")

        try:
            history = await self.store.load_history(observation.peer_hash)
            updated_history, endpoint_changed = self._append_observation(history, observation)
            await self.store.save_history(
                observation.peer_hash,
                updated_history,
                self.config.history_ttl_seconds,
            )
        except AntiAbuseStoreUnavailable:
            logger.warning(
                "[VPN][anti-abuse][VPN_ANTI_ABUSE_REDIS_DEGRADED] "
                f"user_id={observation.user_id} device_id={observation.device_id} peer_hash={observation.peer_hash}"
            )
            return self._decision(
                observation,
                AntiAbuseDecisionKind.DEGRADED,
                "history_store_unavailable",
                event_type=DeviceSecurityEventType.ANTI_ABUSE_REDIS_DEGRADED,
                history_ips=(),
            )

        if not endpoint_changed:
            return self._decision(
                observation,
                AntiAbuseDecisionKind.OK,
                "same_endpoint_ip",
                history_ips=tuple(entry.ip for entry in updated_history),
            )

        kind = classify_endpoint_history(
            updated_history,
            now=observation.observed_at,
            config=self.config,
        )
        return self._decision_for_kind(observation, kind, updated_history)

    def _append_observation(
        self,
        history: list[EndpointHistoryEntry],
        observation: EndpointObservation,
    ) -> tuple[list[EndpointHistoryEntry], bool]:
        recent = _recent_history(
            history,
            now=observation.observed_at,
            window_seconds=self.config.history_window_seconds,
        )
        entry = EndpointHistoryEntry(ip=observation.ip or "", observed_at=observation.observed_at)
        if recent and recent[-1].ip == entry.ip:
            recent[-1] = entry
            return recent, False
        recent.append(entry)
        return recent, True

    def _decision_for_kind(
        self,
        observation: EndpointObservation,
        kind: AntiAbuseDecisionKind,
        history: list[EndpointHistoryEntry],
    ) -> AntiAbuseDecision:
        history_ips = tuple(entry.ip for entry in history)
        if kind is AntiAbuseDecisionKind.ROAMING:
            logger.info(
                "[VPN][anti-abuse][VPN_ENDPOINT_ROAMING_OBSERVED] "
                f"user_id={observation.user_id} device_id={observation.device_id} peer_hash={observation.peer_hash}"
            )
            return self._decision(observation, kind, "single_or_sequential_roaming", history_ips=history_ips)
        if kind is AntiAbuseDecisionKind.PING_PONG_ABUSE:
            logger.warning(
                "[VPN][anti-abuse][VPN_ENDPOINT_PINGPONG_DETECTED] "
                f"user_id={observation.user_id} device_id={observation.device_id} peer_hash={observation.peer_hash}"
            )
            return self._decision(
                observation,
                kind,
                "alternating_endpoint_ips",
                event_type=DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
                should_enforce=True,
                history_ips=history_ips,
            )
        if kind is AntiAbuseDecisionKind.MULTI_NETWORK_ABUSE:
            logger.warning(
                "[VPN][anti-abuse][VPN_ENDPOINT_MULTI_NETWORK_DETECTED] "
                f"user_id={observation.user_id} device_id={observation.device_id} peer_hash={observation.peer_hash}"
            )
            return self._decision(
                observation,
                kind,
                "too_many_unique_endpoint_ips",
                event_type=DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED,
                should_enforce=True,
                history_ips=history_ips,
            )
        return self._decision(observation, kind, kind.value, history_ips=history_ips)

    def _decision(
        self,
        observation: EndpointObservation,
        kind: AntiAbuseDecisionKind,
        reason: str,
        *,
        event_type: DeviceSecurityEventType | None = None,
        should_enforce: bool = False,
        history_ips: tuple[str, ...] = (),
    ) -> AntiAbuseDecision:
        return AntiAbuseDecision(
            kind=kind,
            reason=reason,
            peer_hash=observation.peer_hash,
            user_id=observation.user_id,
            device_id=observation.device_id,
            ip=observation.ip,
            history_ips=history_ips,
            event_type=event_type,
            should_enforce=should_enforce,
        )
# END_BLOCK: AntiAbuseAnalyzer


# START_BLOCK: AntiAbuseEnforcer
class AntiAbuseEnforcer:
    """Apply soft auto-rotation for confirmed abuse decisions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        store: InMemoryEndpointHistoryStore | RedisEndpointHistoryStore,
        config: AntiAbuseConfig,
    ) -> None:
        self.session = session
        self.store = store
        self.config = config

    async def enforce(
        self,
        *,
        decision: AntiAbuseDecision,
        device: UserDevice,
        client: VPNClient,
    ) -> bool:
        """Rotate one device config when abuse is confirmed and mode permits."""
        if not decision.should_enforce or self.config.mode is not AntiAbuseMode.AUTO_ROTATE:
            return False

        try:
            acquired = await self.store.acquire_cooldown_lock(
                int(device.id),
                self.config.enforcement_cooldown_seconds,
            )
        except AntiAbuseStoreUnavailable:
            await self._record_event(
                device=device,
                event_type=DeviceSecurityEventType.ANTI_ABUSE_REDIS_DEGRADED,
                severity=DeviceEventSeverity.WARNING,
                details_json=decision.details_json(),
            )
            logger.warning(
                "[VPN][anti-abuse][VPN_ANTI_ABUSE_REDIS_DEGRADED] "
                f"user_id={device.user_id} device_id={device.id} peer_hash={decision.peer_hash}"
            )
            return False

        if not acquired:
            await self._record_event(
                device=device,
                event_type=DeviceSecurityEventType.ANTI_ABUSE_COOLDOWN_SKIPPED,
                severity=DeviceEventSeverity.WARNING,
                details_json=decision.details_json(),
            )
            logger.warning(
                "[VPN][anti-abuse][VPN_ANTI_ABUSE_ENFORCEMENT_SKIPPED_COOLDOWN] "
                f"user_id={device.user_id} device_id={device.id} peer_hash={decision.peer_hash}"
            )
            return False

        await self._record_event(
            device=device,
            event_type=DeviceSecurityEventType.ANTI_ABUSE_AUTO_ROTATE_STARTED,
            severity=DeviceEventSeverity.WARNING,
            details_json=decision.details_json(),
        )
        logger.warning(
            "[VPN][anti-abuse][VPN_ANTI_ABUSE_AUTO_ROTATE_STARTED] "
            f"user_id={device.user_id} device_id={device.id} client_id={client.id} peer_hash={decision.peer_hash}"
        )

        policy = DeviceAccessPolicyService(self.session)
        vpn = VPNService(self.session)
        await policy.rotate_device_config(device, reason=f"anti_abuse:{decision.kind.value}")
        await vpn.provision_device_client(int(device.user_id), int(device.id), reprovision=True)

        await self._record_event(
            device=device,
            event_type=DeviceSecurityEventType.ANTI_ABUSE_AUTO_ROTATE_COMPLETED,
            severity=DeviceEventSeverity.WARNING,
            details_json=decision.details_json(),
        )
        logger.warning(
            "[VPN][anti-abuse][VPN_ANTI_ABUSE_AUTO_ROTATE_COMPLETED] "
            f"user_id={device.user_id} device_id={device.id} client_id={client.id} peer_hash={decision.peer_hash}"
        )
        return True

    async def _record_event(
        self,
        *,
        device: UserDevice,
        event_type: DeviceSecurityEventType,
        severity: DeviceEventSeverity,
        details_json: str,
    ) -> DeviceSecurityEvent:
        event = DeviceSecurityEvent(
            user_id=int(device.user_id),
            device_id=int(device.id),
            event_type=event_type,
            severity=severity,
            details_json=details_json,
        )
        self.session.add(event)
        await self.session.flush()
        logger.info(
            "[VPN][device][VPN_DEVICE_AUDIT_RECORDED] "
            f"user_id={device.user_id} device_id={device.id} event_type={event_type.value} severity={severity.value}"
        )
        return event
# END_BLOCK: AntiAbuseEnforcer


def hash_peer_public_key(public_key: str) -> str:
    """Hash peer public key for logs and Redis keys."""
    return hashlib.sha256(public_key.encode("utf-8")).hexdigest()[:24]


def _history_key(peer_hash: str) -> str:
    return f"anti_abuse:peer:{peer_hash}:history"


def _cooldown_key(device_id: int) -> str:
    return f"anti_abuse:device:{device_id}:cooldown"


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _recent_history(
    history: list[EndpointHistoryEntry],
    *,
    now: datetime,
    window_seconds: int,
) -> list[EndpointHistoryEntry]:
    cutoff = _coerce_datetime(now) - timedelta(seconds=window_seconds)
    return [entry for entry in history if _coerce_datetime(entry.observed_at) >= cutoff]


def _has_ping_pong_pattern(ips: list[str], *, min_alternations: int) -> bool:
    if len(ips) < min_alternations:
        return False

    for start in range(0, len(ips) - min_alternations + 1):
        segment = ips[start : start + min_alternations]
        if len(set(segment)) != 2:
            continue
        if all(segment[index] != segment[index - 1] for index in range(1, len(segment))) and all(
            segment[index] == segment[index - 2] for index in range(2, len(segment))
        ):
            return True
    return False
