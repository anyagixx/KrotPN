"""
MODULE_CONTRACT
- PURPOSE: Verify admin-only device control endpoints for list, block, unblock, rotate and revoke flows.
- SCOPE: Admin dependency overrides, response-shape checks and targeted mutation orchestration around device actions.
- DEPENDS: M-001 dependency overrides, M-006 admin-api, M-021 device-access-policy, M-024 device-admin-control.
- LINKS: V-M-024.

MODULE_MAP
- _build_client: Constructs a FastAPI test client with admin and DB dependency overrides.
- test_list_admin_devices_returns_device_table_payload: Verifies device table payload is exposed to admins.
- test_block_unblock_rotate_and_revoke_admin_device: Verifies admin actions target one device and reuse the shared serializer.

CHANGE_SUMMARY
- 2026-03-27: Added admin device-control API tests for list and mutation flows.
"""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin import router as admin_router_module
from app.core import get_current_admin
from app.core.database import get_session


class DummySession:
    async def get(self, model, object_id):
        return SimpleNamespace(id=7, email="user@example.com", display_name="User 7")


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_router_module.router)

    async def override_session():
        yield DummySession()

    async def current_admin_override():
        class Admin:
            id = 99
            is_active = True

        return Admin()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_admin] = current_admin_override
    return TestClient(app)


def test_list_admin_devices_returns_device_table_payload(monkeypatch):
    async def fake_list_admin_devices(session, *, search=""):
        assert search == "iphone"
        return [
            {
                "id": 5,
                "user_id": 7,
                "user_email": "user@example.com",
                "user_display_name": "User 7",
                "name": "Family iPhone",
                "platform": "ios",
                "status": "active",
                "config_version": 1,
                "active_peer_count": 1,
                "recent_event_types": ["device_created"],
            }
        ]

    monkeypatch.setattr(admin_router_module, "_list_admin_devices", fake_list_admin_devices)
    client = _build_client()

    response = client.get("/api/admin/devices?search=iphone")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Family iPhone"
    assert body["items"][0]["recent_event_types"] == ["device_created"]


def test_block_unblock_rotate_and_revoke_admin_device(monkeypatch):
    device = SimpleNamespace(id=5, user_id=7, status=SimpleNamespace(value="active"), config_version=1)
    serialized_statuses: list[str] = []
    rotated_calls: list[tuple[int, int, bool]] = []

    class StubPolicyService:
        def __init__(self, session):
            self.session = session

        async def block_device(self, target, *, reason=""):
            target.status = SimpleNamespace(value="blocked")
            return target

        async def unblock_device(self, target, *, reason=""):
            target.status = SimpleNamespace(value="active")
            return target

        async def rotate_device_config(self, target, *, reason=""):
            target.config_version += 1
            return target

        async def revoke_device(self, target, *, reason=""):
            target.status = SimpleNamespace(value="revoked")
            return target

    class StubVPNService:
        def __init__(self, session):
            self.session = session

        async def provision_device_client(self, user_id, device_id, *, reprovision=False):
            rotated_calls.append((user_id, device_id, reprovision))
            return None

    async def fake_get_admin_device_or_none(session, device_id):
        assert device_id == 5
        return device

    async def fake_serialize(session, *, device, user):
        serialized_statuses.append(device.status.value)
        return {
            "id": device.id,
            "user_id": device.user_id,
            "user_email": user.email,
            "user_display_name": user.display_name,
            "status": device.status.value,
            "config_version": device.config_version,
        }

    monkeypatch.setattr(admin_router_module, "DeviceAccessPolicyService", StubPolicyService)
    monkeypatch.setattr(admin_router_module, "VPNService", StubVPNService)
    monkeypatch.setattr(admin_router_module, "_get_admin_device_or_none", fake_get_admin_device_or_none)
    monkeypatch.setattr(admin_router_module, "_serialize_admin_device", fake_serialize)
    client = _build_client()

    block_response = client.post("/api/admin/devices/5/block")
    unblock_response = client.post("/api/admin/devices/5/unblock")
    rotate_response = client.post("/api/admin/devices/5/rotate")
    revoke_response = client.delete("/api/admin/devices/5")

    assert block_response.status_code == 200
    assert block_response.json()["status"] == "blocked"
    assert unblock_response.status_code == 200
    assert unblock_response.json()["status"] == "active"
    assert rotate_response.status_code == 200
    assert rotate_response.json()["config_version"] == 2
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"
    assert rotated_calls == [(7, 5, True)]
    assert serialized_statuses == ["blocked", "active", "active", "revoked"]
