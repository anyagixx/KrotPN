"""MTProto IP observability tests.

# FILE: backend/tests/test_mtproto_ip_observability.py
# VERSION: 1.2.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify encrypted admin-only MTProto client IP observability and 90-day retention
#   SCOPE: Telemetry handoff, Fernet encryption, current/last IP derivation, source-unavailable behavior,
#          RU SNI-router real-IP ingestion, trusted proxy-hop filtering, and prune policy
#   DEPENDS: M-061, M-054, M-042
#   LINKS: V-M-061, V-M-054
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _create_assignment - Persist one verified user and MTProto assignment
#   test_ip_observations_are_encrypted_and_admin_scoped - Covers encrypted upsert and admin decrypt list
#   test_ip_retention_and_source_unavailable_are_deterministic - Covers prune and no-guess behavior
#   test_router_observations_capture_real_client_ip_and_ignore_router_hop - Covers RU SNI-router handoff
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Assert trusted router-hop IP observations are skipped before telemetry persistence.
#   LAST_CHANGE: v1.1.0 - Added RU SNI-router real client IP ingestion and router-hop filtering verification.
#   LAST_CHANGE: v1.0.0 - Added Phase-43 IP observability verification
# END_CHANGE_SUMMARY
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as security_mod
from app.core.config import settings
from app.core.database import get_session
from app.mtproto.ip_observability import (
    apply_ip_retention,
    current_ip_summary,
    list_user_ip_observations,
)
from app.mtproto.models import MTProtoAssignment
from app.mtproto.router import router as mtproto_router
from app.mtproto.usage_models import MTProtoIPObservation, MTProtoUsageEventType
from app.mtproto.usage_repository import MTProtoTelemetryEvent, ingest_telemetry_batch
from app.users.models import User


# START_BLOCK_TEST_HELPERS
@pytest.fixture(autouse=True)
def _phase43_encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(security_mod.settings, "data_encryption_key", key)
    security_mod._fernet = None
    yield
    security_mod._fernet = None


async def _create_assignment(
    session: AsyncSession,
    *,
    email: str = "ip-owner@example.com",
    sni: str = "u-ipobserver.krotpn.xyz",
) -> tuple[User, MTProtoAssignment]:
    user = User(email=email, email_verified=True, is_active=True)
    session.add(user)
    await session.flush()
    assignment = MTProtoAssignment(user_id=int(user.id), sni=sni, rotation_marker="v1")
    session.add(assignment)
    await session.flush()
    await session.refresh(assignment)
    return user, assignment


def _build_router_client(session: AsyncSession) -> TestClient:
    app = FastAPI()
    app.include_router(mtproto_router)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)
# END_BLOCK_TEST_HELPERS


# START_BLOCK_IP_OBSERVABILITY_TESTS
@pytest.mark.asyncio
async def test_ip_observations_are_encrypted_and_admin_scoped(db_session: AsyncSession):
    user, assignment = await _create_assignment(db_session)
    now = datetime.now(timezone.utc)
    raw_ip = "203.0.113.44"

    await ingest_telemetry_batch(
        db_session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id="ip-1",
                event_type=MTProtoUsageEventType.HANDSHAKE,
                observed_at=now,
                assignment_id=int(assignment.id),
                client_ip=raw_ip,
                connection_count=2,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="ip-2",
                event_type=MTProtoUsageEventType.ACTIVE_CONNECTION,
                observed_at=now + timedelta(seconds=1),
                assignment_id=int(assignment.id),
                client_ip=raw_ip,
                connection_count=2,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="ip-3",
                event_type=MTProtoUsageEventType.CLOSE,
                observed_at=now + timedelta(seconds=2),
                assignment_id=int(assignment.id),
                client_ip=raw_ip,
                connection_count=2,
            ),
        ],
    )

    result = await db_session.execute(select(MTProtoIPObservation))
    observation = result.scalar_one()

    assert observation.encrypted_ip != raw_ip
    assert raw_ip not in str(observation)
    assert observation.ip_hash != raw_ip
    assert observation.ip_prefix == "203.0.113.0/24"
    assert observation.current_active is False
    assert observation.connection_count == 2

    history = await list_user_ip_observations(
        db_session,
        assignment_id=int(assignment.id),
        user_id=int(user.id),
        admin_id=99,
    )
    summary = await current_ip_summary(
        db_session,
        assignment_id=int(assignment.id),
        user_id=int(user.id),
        admin_id=99,
    )

    assert history["total"] == 1
    assert history["items"][0]["ip_address"] == raw_ip
    assert summary["last_ip"]["ip_address"] == raw_ip
    assert summary["current_ips"] == []


@pytest.mark.asyncio
async def test_ip_retention_and_source_unavailable_are_deterministic(db_session: AsyncSession):
    user, assignment = await _create_assignment(db_session, email="ip-retention@example.com")
    now = datetime.now(timezone.utc)

    await ingest_telemetry_batch(
        db_session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id="ip-missing",
                event_type=MTProtoUsageEventType.HANDSHAKE,
                observed_at=now,
                assignment_id=int(assignment.id),
            ),
        ],
    )
    empty_summary = await current_ip_summary(
        db_session,
        assignment_id=int(assignment.id),
        user_id=int(user.id),
    )
    assert empty_summary["source_status"] == "source_ip_unavailable"

    await ingest_telemetry_batch(
        db_session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id="ip-old",
                event_type=MTProtoUsageEventType.HANDSHAKE,
                observed_at=now - timedelta(days=120),
                assignment_id=int(assignment.id),
                client_ip="198.51.100.17",
                connection_count=1,
            ),
        ],
    )
    assert (await db_session.execute(select(MTProtoIPObservation))).scalars().first() is not None

    deleted = await apply_ip_retention(db_session, retention_days=90, now=now)
    assert deleted == 1
    result = await db_session.execute(select(MTProtoIPObservation))
    assert list(result.scalars().all()) == []


@pytest.mark.asyncio
async def test_router_observations_capture_real_client_ip_and_ignore_router_hop(
    db_session: AsyncSession,
    monkeypatch,
):
    user, assignment = await _create_assignment(
        db_session,
        email="router-ip-owner@example.com",
        sni="u-abcdef123456.krotpn.xyz",
    )
    monkeypatch.setattr(settings, "mtproto_runtime_token", "router-token-with-enough-length")
    monkeypatch.setattr(settings, "mtproto_router_trusted_proxy_ips", "82.146.61.250")
    client = _build_router_client(db_session)

    rejected = client.post(
        "/api/v1/mtproto/router-observations",
        json={"events": []},
        headers={"x-krotpn-mtproto-token": "wrong-token"},
    )
    accepted = client.post(
        "/api/v1/mtproto/router-observations",
        json={
            "events": [
                {
                    "runtime_event_id": "ru-sni-real-client-1",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "sni": assignment.sni,
                    "client_ip": "203.0.113.88",
                    "connection_count": 1,
                },
                {
                    "runtime_event_id": "ru-sni-router-hop-1",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "sni": assignment.sni,
                    "client_ip": "82.146.61.250",
                    "connection_count": 1,
                },
            ]
        },
        headers={"x-krotpn-mtproto-token": "router-token-with-enough-length"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["written_count"] == 1
    assert accepted.json()["skipped_count"] == 1

    history = await list_user_ip_observations(
        db_session,
        assignment_id=int(assignment.id),
        user_id=int(user.id),
        admin_id=99,
    )
    summary = await current_ip_summary(
        db_session,
        assignment_id=int(assignment.id),
        user_id=int(user.id),
        admin_id=99,
    )

    assert history["total"] == 1
    assert history["items"][0]["ip_address"] == "203.0.113.88"
    assert summary["last_ip"]["ip_address"] == "203.0.113.88"
    assert "82.146.61.250" not in str(history)
# END_BLOCK_IP_OBSERVABILITY_TESTS
