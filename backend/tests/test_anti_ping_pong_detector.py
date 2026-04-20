"""
MODULE_CONTRACT
- PURPOSE: Verify M-031 anti-ping-pong abuse classification and soft enforcement.
- SCOPE: Endpoint normalization, bounded history classification, Redis-degraded fallback, cooldown and auto-rotation side effects.
- DEPENDS: M-001 settings/database, M-003 VPN provisioning, M-020 device registry, M-021 device policy, M-025 audit log, M-031 anti-ping-pong-abuse.
- LINKS: V-M-031.

MODULE_MAP
- test_normalize_endpoint_ip_ignores_nat_port_changes: Verifies IP normalization ignores port churn.
- test_single_endpoint_transition_is_roaming_not_abuse: Verifies Wi-Fi to LTE style transition does not enforce.
- test_ping_pong_pattern_is_abuse: Verifies A-B-A-B alternation emits enforcement decision.
- test_ping_pong_window_limits_old_observations: Verifies configured ping-pong window is enforced.
- test_multi_network_threshold_is_abuse: Verifies excessive unique IP churn emits abuse decision.
- test_store_failure_degrades_without_enforcement: Verifies Redis/store outage returns degraded observe-only decision.
- test_auto_rotate_enforcer_respects_cooldown: Verifies one confirmed abuse rotates once and cooldown suppresses repeats.

CHANGE_SUMMARY
- 2026-04-20: Added M-031 anti-ping-pong detector and enforcement tests.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.devices.models import (
    DeviceSecurityEvent,
    DeviceSecurityEventType,
    DeviceStatus,
    UserDevice,
)
from app.vpn import anti_abuse as anti_abuse_mod
from app.vpn.anti_abuse import (
    AntiAbuseAnalyzer,
    AntiAbuseConfig,
    AntiAbuseDecision,
    AntiAbuseDecisionKind,
    AntiAbuseEnforcer,
    AntiAbuseMode,
    AntiAbuseStoreUnavailable,
    EndpointHistoryEntry,
    EndpointObservation,
    InMemoryEndpointHistoryStore,
    classify_endpoint_history,
    hash_peer_public_key,
    normalize_endpoint_ip,
)
from app.vpn.models import VPNClient


class FailingEndpointHistoryStore(InMemoryEndpointHistoryStore):
    async def load_history(self, peer_hash: str) -> list[EndpointHistoryEntry]:
        raise AntiAbuseStoreUnavailable("redis unavailable")


def _config(*, mode: AntiAbuseMode = AntiAbuseMode.OBSERVE) -> AntiAbuseConfig:
    return AntiAbuseConfig(
        mode=mode,
        history_window_seconds=300,
        history_ttl_seconds=900,
        pingpong_window_seconds=120,
        pingpong_min_alternations=4,
        unique_ip_threshold=4,
        enforcement_cooldown_seconds=900,
    )


async def _analyze_endpoint(
    analyzer: AntiAbuseAnalyzer,
    *,
    public_key: str = "peer-public-key",
    endpoint: str,
    observed_at: datetime,
) -> AntiAbuseDecision:
    return await analyzer.analyze(
        EndpointObservation.from_peer(
            public_key=public_key,
            user_id=1,
            device_id=2,
            endpoint=endpoint,
            observed_at=observed_at,
        )
    )


def test_normalize_endpoint_ip_ignores_nat_port_changes():
    assert normalize_endpoint_ip("198.51.100.7:51820") == "198.51.100.7"
    assert normalize_endpoint_ip("198.51.100.7:49000") == "198.51.100.7"
    assert normalize_endpoint_ip("[2001:db8::1]:51820") == "2001:db8::1"
    assert normalize_endpoint_ip("none") is None


@pytest.mark.asyncio
async def test_single_endpoint_transition_is_roaming_not_abuse():
    analyzer = AntiAbuseAnalyzer(store=InMemoryEndpointHistoryStore(), config=_config())
    now = datetime.now(timezone.utc)

    first = await _analyze_endpoint(analyzer, endpoint="203.0.113.1:51820", observed_at=now)
    second = await _analyze_endpoint(
        analyzer,
        endpoint="198.51.100.7:51820",
        observed_at=now + timedelta(seconds=45),
    )

    assert first.kind is AntiAbuseDecisionKind.OK
    assert second.kind is AntiAbuseDecisionKind.ROAMING
    assert second.should_enforce is False
    assert second.event_type is None


@pytest.mark.asyncio
async def test_ping_pong_pattern_is_abuse():
    analyzer = AntiAbuseAnalyzer(store=InMemoryEndpointHistoryStore(), config=_config())
    now = datetime.now(timezone.utc)

    decision = None
    for index, endpoint in enumerate(
        [
            "203.0.113.1:51820",
            "198.51.100.7:51820",
            "203.0.113.1:51820",
            "198.51.100.7:51820",
        ]
    ):
        decision = await _analyze_endpoint(
            analyzer,
            endpoint=endpoint,
            observed_at=now + timedelta(seconds=index * 20),
        )

    assert decision is not None
    assert decision.kind is AntiAbuseDecisionKind.PING_PONG_ABUSE
    assert decision.event_type is DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED
    assert decision.should_enforce is True
    assert decision.history_ips == (
        "203.0.113.1",
        "198.51.100.7",
        "203.0.113.1",
        "198.51.100.7",
    )


def test_ping_pong_window_limits_old_observations():
    now = datetime.now(timezone.utc)
    history = [
        EndpointHistoryEntry("203.0.113.1", now - timedelta(seconds=240)),
        EndpointHistoryEntry("198.51.100.7", now - timedelta(seconds=200)),
        EndpointHistoryEntry("203.0.113.1", now - timedelta(seconds=40)),
        EndpointHistoryEntry("198.51.100.7", now),
    ]

    decision = classify_endpoint_history(history, now=now, config=_config())

    assert decision is AntiAbuseDecisionKind.ROAMING


@pytest.mark.asyncio
async def test_multi_network_threshold_is_abuse():
    analyzer = AntiAbuseAnalyzer(store=InMemoryEndpointHistoryStore(), config=_config())
    now = datetime.now(timezone.utc)

    decision = None
    for index, endpoint in enumerate(
        [
            "203.0.113.1:51820",
            "198.51.100.7:51820",
            "192.0.2.44:51820",
            "192.0.2.88:51820",
        ]
    ):
        decision = await _analyze_endpoint(
            analyzer,
            endpoint=endpoint,
            observed_at=now + timedelta(seconds=index * 20),
        )

    assert decision is not None
    assert decision.kind is AntiAbuseDecisionKind.MULTI_NETWORK_ABUSE
    assert decision.event_type is DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED
    assert decision.should_enforce is True


@pytest.mark.asyncio
async def test_store_failure_degrades_without_enforcement():
    analyzer = AntiAbuseAnalyzer(store=FailingEndpointHistoryStore(), config=_config())

    decision = await _analyze_endpoint(
        analyzer,
        endpoint="203.0.113.1:51820",
        observed_at=datetime.now(timezone.utc),
    )

    assert decision.kind is AntiAbuseDecisionKind.DEGRADED
    assert decision.event_type is DeviceSecurityEventType.ANTI_ABUSE_REDIS_DEGRADED
    assert decision.should_enforce is False


@pytest.mark.asyncio
async def test_auto_rotate_enforcer_respects_cooldown(
    monkeypatch: pytest.MonkeyPatch,
):
    class StubSession:
        def __init__(self):
            self.added: list[object] = []

        def add(self, item):
            self.added.append(item)

        async def flush(self):
            return None

    class StubPolicyService:
        def __init__(self, session):
            self.session = session

        async def rotate_device_config(self, target, *, reason=""):
            target.config_version += 1
            self.session.add(
                DeviceSecurityEvent(
                    user_id=int(target.user_id),
                    device_id=int(target.id),
                    event_type=DeviceSecurityEventType.CONFIG_ROTATED,
                    details_json=f'{{"reason":"{reason}"}}',
                )
            )
            return target

    provision_calls: list[tuple[int, int, bool]] = []

    class StubVPNService:
        def __init__(self, session):
            self.session = session

        async def provision_device_client(self, user_id, device_id, *, reprovision=False):
            provision_calls.append((user_id, device_id, reprovision))
            return None

    session = StubSession()
    device = UserDevice(
        id=2,
        user_id=1,
        name="Android",
        platform="android",
        status=DeviceStatus.ACTIVE,
    )
    client = VPNClient(
        id=3,
        user_id=1,
        device_id=2,
        public_key="old-public-key",
        private_key_enc="old-private-key",
        address="10.10.0.9",
        is_active=True,
    )
    monkeypatch.setattr(anti_abuse_mod, "DeviceAccessPolicyService", StubPolicyService)
    monkeypatch.setattr(anti_abuse_mod, "VPNService", StubVPNService)
    store = InMemoryEndpointHistoryStore()
    enforcer = AntiAbuseEnforcer(
        session,
        store=store,
        config=_config(mode=AntiAbuseMode.AUTO_ROTATE),
    )
    decision = AntiAbuseDecision(
        kind=AntiAbuseDecisionKind.PING_PONG_ABUSE,
        reason="alternating_endpoint_ips",
        peer_hash=hash_peer_public_key(client.public_key),
        user_id=int(device.user_id),
        device_id=int(device.id),
        ip="198.51.100.7",
        history_ips=("203.0.113.1", "198.51.100.7", "203.0.113.1", "198.51.100.7"),
        event_type=DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
        should_enforce=True,
    )

    first_result = await enforcer.enforce(decision=decision, device=device, client=client)
    second_result = await enforcer.enforce(decision=decision, device=device, client=client)
    event_types = [
        event.event_type
        for event in session.added
        if isinstance(event, DeviceSecurityEvent)
    ]

    assert first_result is True
    assert second_result is False
    assert device.config_version == 2
    assert provision_calls == [(int(device.user_id), int(device.id), True)]
    assert DeviceSecurityEventType.CONFIG_ROTATED in event_types
    assert DeviceSecurityEventType.ANTI_ABUSE_AUTO_ROTATE_STARTED in event_types
    assert DeviceSecurityEventType.ANTI_ABUSE_AUTO_ROTATE_COMPLETED in event_types
    assert DeviceSecurityEventType.ANTI_ABUSE_COOLDOWN_SKIPPED in event_types
