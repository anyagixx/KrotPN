"""Official MTProxy secret sync tests.

# FILE: backend/tests/test_mtproxy_secret_sync.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify official MTProxy manifest rendering, runtime sync, and redaction guarantees
#   SCOPE: Active official assignment filtering, raw-runtime/dd-owner separation, HTTP request shape, revoke replay, and degraded apply
#   DEPENDS: M-053, M-042, M-001, M-002
#   LINKS: V-M-053, V-M-042, V-M-001
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _settings - Build deterministic MTProxy secret settings
#   _create_assignment - Create user-linked MTProto assignment fixtures
#   test_secret_manifest_sync_redacts_safe_output_and_sends_raw_runtime_secrets - Covers manifest rendering
#   test_http_secret_adapter_posts_manifest_without_tg_link_material - Covers private runtime HTTP request shape
#   test_revoke_assignment_secret_replays_active_manifest_without_revoked_assignment - Covers revoke replay
#   test_adapter_failure_returns_degraded_without_raw_secret - Covers degraded apply redaction
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-40 official MTProxy secret sync verification.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus, MTProtoCredentialMode
from app.mtproto.official_secrets import (
    HTTPMTProxySecretAdapter,
    InMemoryMTProxySecretAdapter,
    MTProxySecretManifest,
    MTProxySecretManifestEntry,
    MTProxySecretSyncService,
    secret_fingerprint,
)
from app.mtproto.runtime_bridge import MTProtoBridgeStatus
from app.users.models import User


BASE_SECRET = "0123456789abcdef0123456789abcdef"
SECRET_SALT = "abcdef0123456789abcdef0123456789"


# START_BLOCK_TEST_HELPERS
def _settings(**overrides) -> Settings:
    values = {
        "secret_key": "test-secret-key-with-enough-length",
        "mtproto_base_domain": "krotpn.xyz",
        "mtproto_proxy_port": 443,
        "mtproto_base_secret_hex": BASE_SECRET,
        "mtproto_secret_salt": SECRET_SALT,
        "mtproto_sni_prefix": "u",
        "mtproto_rotation_marker": "v1",
    }
    values.update(overrides)
    return Settings(**values)


async def _create_assignment(
    session: AsyncSession,
    email: str,
    sni: str,
    *,
    status: MTProtoAssignmentStatus = MTProtoAssignmentStatus.ACTIVE,
    credential_mode: MTProtoCredentialMode = MTProtoCredentialMode.OFFICIAL_SECURE,
) -> MTProtoAssignment:
    user = User(email=email, email_verified=True, is_active=True)
    session.add(user)
    await session.flush()
    assignment = MTProtoAssignment(
        user_id=int(user.id),
        sni=sni,
        credential_mode=credential_mode,
        status=status,
        rotation_marker="v1",
    )
    session.add(assignment)
    await session.flush()
    await session.refresh(assignment)
    return assignment
# END_BLOCK_TEST_HELPERS


# START_BLOCK_OFFICIAL_SECRET_SYNC_TESTS
@pytest.mark.asyncio
async def test_secret_manifest_sync_redacts_safe_output_and_sends_raw_runtime_secrets(
    db_session: AsyncSession,
):
    first = await _create_assignment(
        db_session,
        "official-active-one@example.com",
        "u-official111.krotpn.xyz",
    )
    second = await _create_assignment(
        db_session,
        "official-active-two@example.com",
        "u-official222.krotpn.xyz",
    )
    await _create_assignment(
        db_session,
        "official-disabled@example.com",
        "u-disabled333.krotpn.xyz",
        status=MTProtoAssignmentStatus.DISABLED,
    )
    await _create_assignment(
        db_session,
        "official-legacy@example.com",
        "u-legacy444.krotpn.xyz",
        credential_mode=MTProtoCredentialMode.DERIVED_PER_SNI,
    )
    adapter = InMemoryMTProxySecretAdapter()
    service = MTProxySecretSyncService(db_session, app_settings=_settings(), adapter=adapter)

    result = await service.apply_active_manifest()

    assert result.status == MTProtoBridgeStatus.ACTIVATED
    assert result.active_count == 2
    assert adapter.applied_manifest is not None
    runtime_entries = adapter.applied_manifest.entries
    assert {entry.assignment_id for entry in runtime_entries} == {first.id, second.id}
    assert all(len(entry.secret_hex) == 32 for entry in runtime_entries)
    assert all(len("dd" + entry.secret_hex) == 34 for entry in runtime_entries)

    safe_payload = adapter.applied_manifest.to_safe_dict()
    safe_text = str(safe_payload)
    assert "secret_hex" not in safe_text
    assert BASE_SECRET not in safe_text
    assert SECRET_SALT not in safe_text


@pytest.mark.asyncio
async def test_http_secret_adapter_posts_manifest_without_tg_link_material():
    raw_secret = "1" * 32
    manifest = MTProxySecretManifest(
        entries=(
            MTProxySecretManifestEntry(
                assignment_id=10,
                user_id=20,
                sni="u-http111111.krotpn.xyz",
                secret_hex=raw_secret,
                secret_fingerprint=secret_fingerprint(raw_secret),
            ),
        ),
        generated_at=datetime.now(UTC),
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/secrets/apply"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["secrets"][0]["secret_hex"] == raw_secret
            payload_text = str(payload)
            assert "tg://proxy" not in payload_text
            assert "https://t.me/proxy" not in payload_text
            assert "dd" + raw_secret not in payload_text
            return httpx.Response(200, json={"status": "activated"})
        if request.url.path.endswith("/health"):
            return httpx.Response(200, json={"status": "healthy", "active_count": 1})
        return httpx.Response(404, json={"status": "not_found"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://127.0.0.1",
    ) as client:
        adapter = HTTPMTProxySecretAdapter(
            base_url="http://127.0.0.1:18080/krotpn/mtproto/policy",
            policy_token="test-runtime-token-with-enough-length",
            timeout=1.0,
            client=client,
        )
        result = await adapter.apply_manifest(manifest)
        health = await adapter.health()

    assert result.status == MTProtoBridgeStatus.ACTIVATED
    assert health.status == MTProtoBridgeStatus.HEALTHY
    assert [request.url.path for request in requests] == [
        "/krotpn/mtproto/policy/secrets/apply",
        "/krotpn/mtproto/policy/health",
    ]
    assert all(
        request.headers["x-krotpn-mtproto-token"]
        == "test-runtime-token-with-enough-length"
        for request in requests
    )


@pytest.mark.asyncio
async def test_revoke_assignment_secret_replays_active_manifest_without_revoked_assignment(
    db_session: AsyncSession,
):
    assignment = await _create_assignment(
        db_session,
        "official-revoke@example.com",
        "u-revoke55555.krotpn.xyz",
    )
    adapter = InMemoryMTProxySecretAdapter()
    service = MTProxySecretSyncService(db_session, app_settings=_settings(), adapter=adapter)

    await service.apply_active_manifest()
    assignment.status = MTProtoAssignmentStatus.DISABLED
    await db_session.flush()

    result = await service.revoke_assignment_secret(assignment)

    assert result.status == MTProtoBridgeStatus.REVOKED
    assert result.active_count == 0
    assert adapter.applied_manifest is not None
    assert adapter.applied_manifest.active_count == 0


@pytest.mark.asyncio
async def test_adapter_failure_returns_degraded_without_raw_secret():
    raw_secret = "2" * 32
    manifest = MTProxySecretManifest(
        entries=(
            MTProxySecretManifestEntry(
                assignment_id=11,
                user_id=21,
                sni="u-fail111111.krotpn.xyz",
                secret_hex=raw_secret,
                secret_fingerprint=secret_fingerprint(raw_secret),
            ),
        ),
        generated_at=datetime.now(UTC),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "degraded"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://127.0.0.1",
    ) as client:
        adapter = HTTPMTProxySecretAdapter(
            base_url="http://127.0.0.1:18080/krotpn/mtproto/policy",
            policy_token="test-runtime-token-with-enough-length",
            timeout=1.0,
            client=client,
        )
        result = await adapter.apply_manifest(manifest)

    safe_payload = result.to_safe_dict()
    assert result.status == MTProtoBridgeStatus.DEGRADED
    assert raw_secret not in str(safe_payload)
    assert "dd" + raw_secret not in str(safe_payload)
# END_BLOCK_OFFICIAL_SECRET_SYNC_TESTS
