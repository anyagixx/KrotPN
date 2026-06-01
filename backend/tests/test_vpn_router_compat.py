"""
MODULE_CONTRACT
- PURPOSE: Verify versioned VPN compatibility routes and primary-device provisioning behavior.
- SCOPE: Public /api/v1/vpn servers/nodes wrappers and get_or_provision_user_client routing.
- DEPENDS: M-022 device provisioning API, M-003 VPN router/service, V-M-022 verification.
- LINKS: docs/modules/M-022.xml, docs/verification/V-M-022.xml.

MODULE_MAP
- test_public_servers_endpoint_is_compat_wrapper: Verifies /api/v1/vpn/servers projects entry nodes into legacy server shape.
- test_public_nodes_endpoint_returns_route_aware_nodes: Verifies /api/v1/vpn/nodes returns active route-aware nodes.
- test_get_or_provision_user_client_prefers_active_primary_device: Verifies active primary devices are preferred over legacy user clients.
- test_config_download_uses_mobile_safe_attachment_headers: Verifies .conf download headers prevent mobile .txt suffixing.
- test_config_download_filename_sanitizer_forces_single_conf_suffix: Verifies unsafe filename candidates are normalized.
- test_config_download_requires_authenticated_user: Verifies the config download route stays authenticated.

CHANGE_SUMMARY
- 2026-06-01: Added Phase-48 mobile-safe .conf download MIME/header coverage.
- 2026-05-19: Aligned compatibility route coverage with /api/v1 VPN router prefix for Phase-28 debt closure.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import get_current_user
from app.core.database import get_session
from app.devices.models import DeviceStatus, UserDevice
from app.vpn import router as vpn_router_module


class DummySession:
    pass


class StubVPNService:
    def __init__(self, session):
        self.session = session

    async def get_node_statuses(self):
        return [
            {
                "id": 10,
                "name": "RU Entry Node",
                "role": "entry",
                "country_code": "RU",
                "location": "Russia",
                "endpoint": "1.1.1.1",
                "port": 51821,
                "public_key": "entry-pub",
                "is_active": True,
                "is_online": True,
                "is_entry_node": True,
                "is_exit_node": False,
                "current_clients": 4,
                "max_clients": 50,
                "load_percent": 8.0,
            },
            {
                "id": 11,
                "name": "DE Exit Node",
                "role": "exit",
                "country_code": "DE",
                "location": "Germany",
                "endpoint": "2.2.2.2",
                "port": 51821,
                "public_key": "exit-pub",
                "is_active": True,
                "is_online": True,
                "is_entry_node": False,
                "is_exit_node": True,
                "current_clients": 4,
                "max_clients": 50,
                "load_percent": 8.0,
            },
        ]


def _build_app(*, with_current_user: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(vpn_router_module.router)

    async def override_session():
        yield DummySession()

    async def current_user_override():
        class User:
            id = 1
            is_active = True
        return User()

    app.dependency_overrides[get_session] = override_session
    if with_current_user:
        app.dependency_overrides[get_current_user] = current_user_override
    return TestClient(app)


def test_public_servers_endpoint_is_compat_wrapper(monkeypatch):
    monkeypatch.setattr(vpn_router_module, "VPNService", StubVPNService)
    client = _build_app()

    response = client.get("/api/v1/vpn/servers")

    assert response.status_code == 200
    body = response.json()
    assert len(body["servers"]) == 1
    assert body["servers"][0]["name"] == "RU Entry Node"
    assert body["servers"][0]["location"] == "Russia"


def test_public_nodes_endpoint_returns_route_aware_nodes(monkeypatch):
    monkeypatch.setattr(vpn_router_module, "VPNService", StubVPNService)
    client = _build_app()

    response = client.get("/api/v1/vpn/nodes")

    assert response.status_code == 200
    body = response.json()
    assert len(body["nodes"]) == 2
    assert {item["role"] for item in body["nodes"]} == {"entry", "exit"}


@pytest.mark.asyncio
async def test_get_or_provision_user_client_prefers_active_primary_device(monkeypatch):
    device = UserDevice(
        id=21,
        user_id=1,
        device_key="device-21",
        name="Primary device",
        platform="web-default",
        status=DeviceStatus.ACTIVE,
    )

    class StubVPNService:
        def __init__(self, session):
            self.session = session

        async def get_device_client(self, device_id, active_only=True):
            assert device_id == 21
            assert active_only is True
            return None

        async def provision_device_client(self, user_id, device_id, *, reprovision=False):
            assert user_id == 1
            assert device_id == 21
            assert reprovision is False
            return {"client_id": 99, "device_id": 21}

        async def get_user_client(self, user_id):
            raise AssertionError("legacy user client fallback should not be used when active device exists")

    class StubBillingService:
        def __init__(self, session):
            self.session = session

        async def get_user_subscription(self, user_id):
            assert user_id == 1
            return object()

    class StubDevicePolicyService:
        def __init__(self, session):
            self.session = session

        async def list_user_devices(self, user_id):
            assert user_id == 1
            return [device]

    monkeypatch.setattr(vpn_router_module, "VPNService", StubVPNService)
    monkeypatch.setattr(vpn_router_module, "BillingService", StubBillingService)
    monkeypatch.setattr(vpn_router_module, "DeviceAccessPolicyService", StubDevicePolicyService)

    result = await vpn_router_module.get_or_provision_user_client(1, DummySession())

    assert result == {"client_id": 99, "device_id": 21}


def test_config_download_uses_mobile_safe_attachment_headers(monkeypatch):
    config_text = "[Interface]\nPrivateKey = redacted\nAddress = 10.8.0.2/32\n"

    class StubDownloadVPNService:
        def __init__(self, session):
            self.session = session

        async def get_client_config(self, client):
            assert client.id == 77
            return SimpleNamespace(
                config=config_text,
                server_name="RU",
                server_location="Russia",
                address="10.8.0.2",
                created_at=datetime.now(timezone.utc),
            )

    async def fake_get_or_provision_user_client(user_id, session):
        assert user_id == 1
        return SimpleNamespace(id=77, is_active=True)

    monkeypatch.setattr(vpn_router_module, "VPNService", StubDownloadVPNService)
    monkeypatch.setattr(vpn_router_module, "get_or_provision_user_client", fake_get_or_provision_user_client)
    client = _build_app()

    response = client.get("/api/v1/vpn/config/download")

    assert response.status_code == 200
    assert response.content == config_text.encode("utf-8")
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"]
    assert "private" in response.headers["cache-control"]
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert 'filename="krotpn-1.conf"' in disposition
    assert "filename*=UTF-8''krotpn-1.conf" in disposition
    assert ".conf.txt" not in disposition


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("../evil.conf.txt", "evil.conf"),
        ("krotpn-user.conf.conf.txt", "krotpn-user.conf"),
        ("device/phone\\vpn.txt", "device-phone-vpn.conf"),
        ("", "krotpn-config.conf"),
        ("тест.conf", "krotpn-config.conf"),
    ],
)
def test_config_download_filename_sanitizer_forces_single_conf_suffix(candidate, expected):
    filename = vpn_router_module.sanitize_config_download_filename(candidate)

    assert filename == expected
    assert filename.endswith(".conf")
    assert not filename.endswith(".txt")
    assert "/" not in filename
    assert "\\" not in filename


def test_config_download_requires_authenticated_user():
    client = _build_app(with_current_user=False)

    response = client.get("/api/v1/vpn/config/download")

    assert response.status_code in {401, 403}
