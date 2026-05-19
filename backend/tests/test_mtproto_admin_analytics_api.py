"""MTProto admin analytics API tests.

# FILE: backend/tests/test_mtproto_admin_analytics_api.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify admin-only MTProto analytics and promotion tag API responses are useful and redacted
#   SCOPE: Summary, assignment usage, event list, top users, abuse signals, promotion tag state/update, and role gates
#   DEPENDS: M-057, M-056, M-059
#   LINKS: V-M-057, V-M-059
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _build_client - Build FastAPI admin-router client with DB override
#   _create_user - Create role-aware test users
#   _create_assignment - Persist MTProto assignment
#   _headers - Build JWT auth headers
#   _assert_redacted - Assert admin payloads do not contain forbidden values
#   test_admin_mtproto_analytics_api_is_admin_only_and_redacted - Covers Phase-42 admin API surface
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto admin analytics API tests
# END_CHANGE_SUMMARY
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import router as admin_router_module
from app.core.database import get_session
from app.core.security import create_access_token
from app.mtproto.models import MTProtoAssignment
from app.mtproto.usage_models import MTProtoUsageEventType
from app.mtproto.usage_repository import MTProtoTelemetryEvent, ingest_telemetry_batch
from app.users.models import User, UserRole


FULL_TAG = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


# START_BLOCK_TEST_HELPERS
def _build_client(session: AsyncSession) -> TestClient:
    app = FastAPI()
    app.include_router(admin_router_module.router)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


async def _create_user(
    session: AsyncSession,
    email: str,
    *,
    role: UserRole = UserRole.USER,
) -> User:
    user = User(email=email, role=role, email_verified=True, is_active=True)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_assignment(
    session: AsyncSession,
    user: User,
    sni: str = "u-adminanalytics.krotpn.xyz",
) -> MTProtoAssignment:
    assignment = MTProtoAssignment(user_id=int(user.id), sni=sni, rotation_marker="v1")
    session.add(assignment)
    await session.flush()
    await session.refresh(assignment)
    return assignment


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _assert_redacted(payload: object) -> None:
    payload_text = str(payload)
    assert "tg://proxy" not in payload_text
    assert "https://t.me/proxy" not in payload_text
    assert "secret=" not in payload_text
    assert "MTPROTO_RUNTIME_TOKEN" not in payload_text
    assert FULL_TAG not in payload_text
# END_BLOCK_TEST_HELPERS


# START_BLOCK_ADMIN_ANALYTICS_API_TESTS
@pytest.mark.asyncio
async def test_admin_mtproto_analytics_api_is_admin_only_and_redacted(db_session: AsyncSession):
    admin = await _create_user(db_session, "phase42-admin@example.com", role=UserRole.ADMIN)
    regular = await _create_user(db_session, "phase42-regular@example.com")
    owner = await _create_user(db_session, "phase42-owner@example.com")
    assignment = await _create_assignment(db_session, owner)
    await ingest_telemetry_batch(
        db_session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id="api-1",
                event_type=MTProtoUsageEventType.HANDSHAKE,
                observed_at=datetime.now(timezone.utc),
                assignment_id=int(assignment.id),
                client_ip="203.0.113.99",
                connection_count=1,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="api-2",
                event_type=MTProtoUsageEventType.BYTES,
                observed_at=datetime.now(timezone.utc),
                assignment_id=int(assignment.id),
                bytes_in=10,
                bytes_out=20,
            ),
        ],
    )
    client = _build_client(db_session)

    summary = client.get("/api/v1/admin/mtproto/analytics/summary?days=1", headers=_headers(admin))
    usage = client.get(f"/api/v1/admin/mtproto/assignments/{assignment.id}/usage?days=1", headers=_headers(admin))
    events = client.get("/api/v1/admin/mtproto/analytics/events?days=1", headers=_headers(admin))
    top_users = client.get("/api/v1/admin/mtproto/analytics/top-users?metric=traffic&days=1", headers=_headers(admin))
    abuse = client.get("/api/v1/admin/mtproto/analytics/abuse-signals?days=1", headers=_headers(admin))
    tag_state = client.get("/api/v1/admin/mtproto/promotion-tag", headers=_headers(admin))
    tag_update = client.put(
        "/api/v1/admin/mtproto/promotion-tag",
        json={"tag": FULL_TAG, "confirm": True},
        headers=_headers(admin),
    )
    rejected = client.get("/api/v1/admin/mtproto/analytics/summary", headers=_headers(regular))

    assert summary.status_code == 200
    assert summary.json()["issued_total"] == 1
    assert usage.status_code == 200
    assert usage.json()["assignment"]["sni_masked"] != assignment.sni
    assert events.status_code == 200
    assert events.json()["total"] == 2
    assert top_users.status_code == 200
    assert top_users.json()["items"][0]["user_id"] == owner.id
    assert abuse.status_code == 200
    assert tag_state.status_code == 200
    assert tag_update.status_code == 200
    assert tag_update.json()["masked_tag"] == "aaaa...aaaa"
    assert rejected.status_code == 403
    for payload in [
        summary.json(),
        usage.json(),
        events.json(),
        top_users.json(),
        abuse.json(),
        tag_state.json(),
        tag_update.json(),
    ]:
        _assert_redacted(payload)
# END_BLOCK_ADMIN_ANALYTICS_API_TESTS
