"""KPprotoN runtime bridge tests.

# FILE: backend/tests/test_kpproton_runtime_bridge.py
# VERSION: 1.2.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify safe MTProto runtime policy bridge behavior
#   SCOPE: Policy apply, HTTP live adapter, replay idempotency, degraded mode, health, and redaction
#   DEPENDS: M-044, M-042, M-043
#   LINKS: V-M-044
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_apply_domain_policy_records_active_assignment - Covers successful adapter apply
#   test_revoke_domain_policy_removes_runtime_policy_state - Covers successful adapter revoke
#   test_replay_active_assignments_is_idempotent_and_skips_inactive - Covers replay
#   test_bridge_unavailable_returns_degraded_without_exception - Covers outage path
#   test_http_policy_adapter_posts_apply_and_health_with_token - Covers live sidecar request shape
#   test_inactive_assignment_is_rejected_before_adapter_call - Covers pre-adapter guard
#   test_runtime_health_summary_is_secret_free - Covers safe health payload
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Added Phase-37 HTTP live adapter request-shape coverage
#   LAST_CHANGE: v1.1.0 - Added runtime policy revoke regression coverage for Phase-33 admin revoke
#   LAST_CHANGE: v1.0.0 - Added Phase-30 runtime bridge tests
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.health import build_runtime_health_summary
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus
from app.mtproto.runtime_bridge import (
    HTTPMTProtoPolicyAdapter,
    InMemoryMTProtoPolicyAdapter,
    MTProtoBridgeFailureCode,
    MTProtoBridgeStatus,
    MTProtoDomainPolicy,
    MTProtoRuntimeBridge,
)
from app.users.models import User


# START_BLOCK_TEST_HELPERS
class RecordingPolicyAdapter(InMemoryMTProtoPolicyAdapter):
    """In-memory adapter that records apply calls for idempotency assertions."""

    def __init__(self, *, available: bool = True) -> None:
        super().__init__(available=available)
        self.calls: list[str] = []
        self.revoke_calls: list[str] = []

    async def apply_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        self.calls.append(policy.sni)
        await super().apply_domain_policy(policy)

    async def revoke_domain_policy(self, policy: MTProtoDomainPolicy) -> None:
        self.revoke_calls.append(policy.sni)
        await super().revoke_domain_policy(policy)


async def _create_assignment(
    db_session: AsyncSession,
    email: str,
    sni: str,
    *,
    status: MTProtoAssignmentStatus = MTProtoAssignmentStatus.ACTIVE,
) -> MTProtoAssignment:
    user = User(email=email, email_verified=True, is_active=True)
    db_session.add(user)
    await db_session.flush()

    assignment = MTProtoAssignment(
        user_id=int(user.id),
        sni=sni,
        status=status,
        rotation_marker="v1",
    )
    db_session.add(assignment)
    await db_session.flush()
    await db_session.refresh(assignment)
    return assignment
# END_BLOCK_TEST_HELPERS


# START_BLOCK_RUNTIME_BRIDGE_TESTS
@pytest.mark.asyncio
async def test_apply_domain_policy_records_active_assignment(db_session: AsyncSession):
    assignment = await _create_assignment(
        db_session,
        "bridge-active@example.com",
        "u-active111111.krotpn.xyz",
    )
    adapter = RecordingPolicyAdapter()
    bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)

    result = await bridge.apply_domain_policy(assignment)

    assert result.status == MTProtoBridgeStatus.ACTIVATED
    assert result.assignment_id == assignment.id
    assert adapter.policies[assignment.sni].assignment_id == assignment.id
    assert adapter.calls == [assignment.sni]


@pytest.mark.asyncio
async def test_revoke_domain_policy_removes_runtime_policy_state(db_session: AsyncSession):
    assignment = await _create_assignment(
        db_session,
        "bridge-revoke@example.com",
        "u-revoke22222.krotpn.xyz",
    )
    adapter = RecordingPolicyAdapter()
    bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)

    apply_result = await bridge.apply_domain_policy(assignment)
    assignment.status = MTProtoAssignmentStatus.DISABLED
    revoke_result = await bridge.revoke_domain_policy(assignment)

    assert apply_result.status == MTProtoBridgeStatus.ACTIVATED
    assert revoke_result.status == MTProtoBridgeStatus.REVOKED
    assert revoke_result.to_safe_dict()["status"] == "revoked"
    assert assignment.sni not in adapter.policies
    assert adapter.revoke_calls == [assignment.sni]


@pytest.mark.asyncio
async def test_replay_active_assignments_is_idempotent_and_skips_inactive(
    db_session: AsyncSession,
):
    active_one = await _create_assignment(
        db_session,
        "bridge-active-one@example.com",
        "u-active222222.krotpn.xyz",
    )
    active_two = await _create_assignment(
        db_session,
        "bridge-active-two@example.com",
        "u-active333333.krotpn.xyz",
    )
    await _create_assignment(
        db_session,
        "bridge-disabled@example.com",
        "u-disabled1111.krotpn.xyz",
        status=MTProtoAssignmentStatus.DISABLED,
    )
    await _create_assignment(
        db_session,
        "bridge-superseded@example.com",
        "u-superseded11.krotpn.xyz",
        status=MTProtoAssignmentStatus.SUPERSEDED,
    )
    adapter = RecordingPolicyAdapter()
    bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)

    first = await bridge.replay_active_assignments()
    second = await bridge.replay_active_assignments()

    assert first.processed_count == 4
    assert first.applied_count == 2
    assert first.skipped_count == 2
    assert second.applied_count == 2
    assert set(adapter.policies) == {active_one.sni, active_two.sni}
    assert adapter.calls == [
        active_one.sni,
        active_two.sni,
        active_one.sni,
        active_two.sni,
    ]


@pytest.mark.asyncio
async def test_bridge_unavailable_returns_degraded_without_exception(
    db_session: AsyncSession,
):
    assignment = await _create_assignment(
        db_session,
        "bridge-degraded@example.com",
        "u-degraded111.krotpn.xyz",
    )
    adapter = RecordingPolicyAdapter(available=False)
    bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)

    result = await bridge.apply_domain_policy(assignment)
    health = await bridge.runtime_health()

    assert result.status == MTProtoBridgeStatus.DEGRADED
    assert result.failure_code == MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE
    assert health.status == MTProtoBridgeStatus.DEGRADED
    assert adapter.policies == {}


@pytest.mark.asyncio
async def test_http_policy_adapter_posts_apply_and_health_with_token(
    db_session: AsyncSession,
):
    assignment = await _create_assignment(
        db_session,
        "bridge-http@example.com",
        "u-http1111111.krotpn.xyz",
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/apply"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["sni"] == assignment.sni
            assert "secret" not in payload
            return httpx.Response(200, json={"status": "applied"})
        if request.url.path.endswith("/health"):
            return httpx.Response(200, json={"status": "healthy"})
        return httpx.Response(404, json={"status": "not_found"})

    adapter = HTTPMTProtoPolicyAdapter(
        base_url="http://127.0.0.1:18080/krotpn/mtproto/policy",
        token="test-runtime-token-with-enough-length",
        transport=httpx.MockTransport(handler),
    )
    bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)

    result = await bridge.apply_domain_policy(assignment)
    health = await bridge.runtime_health()

    assert result.status == MTProtoBridgeStatus.ACTIVATED
    assert health.status == MTProtoBridgeStatus.HEALTHY
    assert [request.url.path for request in requests] == [
        "/krotpn/mtproto/policy/apply",
        "/krotpn/mtproto/policy/health",
    ]
    assert all(
        request.headers["x-krotpn-mtproto-token"]
        == "test-runtime-token-with-enough-length"
        for request in requests
    )


@pytest.mark.asyncio
async def test_inactive_assignment_is_rejected_before_adapter_call(db_session: AsyncSession):
    assignment = await _create_assignment(
        db_session,
        "bridge-inactive@example.com",
        "u-inactive111.krotpn.xyz",
        status=MTProtoAssignmentStatus.DISABLED,
    )
    adapter = RecordingPolicyAdapter()
    bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)

    result = await bridge.apply_domain_policy(assignment)

    assert result.status == MTProtoBridgeStatus.SKIPPED
    assert result.failure_code == MTProtoBridgeFailureCode.INVALID_ASSIGNMENT
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_runtime_health_summary_is_secret_free(db_session: AsyncSession):
    adapter = InMemoryMTProtoPolicyAdapter(available=False)
    bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)

    health = await bridge.runtime_health()
    summary = build_runtime_health_summary(health)
    summary_text = str(summary)

    assert summary["status"] == MTProtoBridgeStatus.DEGRADED.value
    assert "tg://proxy" not in summary_text
    assert "0123456789abcdef0123456789abcdef" not in summary_text
    assert "abcdef0123456789abcdef0123456789" not in summary_text
# END_BLOCK_RUNTIME_BRIDGE_TESTS
