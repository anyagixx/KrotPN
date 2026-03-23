import pytest

from app.vpn.models import VPNClient, VPNServer
from app.vpn.service import VPNService


class DummySession:
    async def refresh(self, obj):
        return obj


@pytest.mark.asyncio
async def test_create_client_returns_existing_active_client(monkeypatch):
    service = VPNService(DummySession())
    existing = VPNClient(
        id=1,
        user_id=10,
        server_id=5,
        public_key="pub",
        private_key_enc="enc",
        address="10.10.0.2",
        is_active=True,
    )
    target_server = VPNServer(
        id=5,
        name="RU",
        location="Russia",
        endpoint="1.1.1.1",
        public_key="server-pub",
    )

    async def fake_get_user_client(user_id, active_only=True):
        assert active_only is False
        return existing

    async def fake_get_server(server_id):
        return target_server

    monkeypatch.setattr(service, "get_user_client", fake_get_user_client)
    monkeypatch.setattr(service, "get_server", fake_get_server)

    result = await service.create_client(user_id=10, server_id=5)
    assert result is existing


@pytest.mark.asyncio
async def test_create_client_reactivates_existing_inactive_client(monkeypatch):
    service = VPNService(DummySession())
    existing = VPNClient(
        id=1,
        user_id=10,
        server_id=5,
        public_key="pub",
        private_key_enc="enc",
        address="10.10.0.2",
        is_active=False,
    )
    current_server = VPNServer(
        id=5,
        name="RU",
        location="Russia",
        endpoint="1.1.1.1",
        public_key="server-pub",
        is_active=True,
        is_online=True,
        is_entry_node=True,
    )
    calls: list[str] = []

    async def fake_get_user_client(user_id, active_only=True):
        return existing

    async def fake_select_server(client):
        return current_server

    async def fake_activate(client):
        calls.append("activate")
        client.is_active = True

    monkeypatch.setattr(service, "get_user_client", fake_get_user_client)
    monkeypatch.setattr(service, "_select_server_for_existing_client", fake_select_server)
    monkeypatch.setattr(service, "activate_client", fake_activate)

    result = await service.create_client(user_id=10)
    assert result is existing
    assert existing.is_active is True
    assert calls == ["activate"]


@pytest.mark.asyncio
async def test_create_client_reprovisions_inactive_client_on_new_server(monkeypatch):
    service = VPNService(DummySession())
    existing = VPNClient(
        id=1,
        user_id=10,
        server_id=5,
        public_key="pub",
        private_key_enc="enc",
        address="10.10.0.2",
        is_active=False,
    )
    new_server = VPNServer(
        id=8,
        name="DE",
        location="Germany",
        endpoint="2.2.2.2",
        public_key="server-pub-2",
    )
    calls: list[str] = []

    async def fake_get_user_client(user_id, active_only=True):
        return existing

    async def fake_select_server(client):
        return new_server

    async def fake_reprovision(client, server):
        calls.append(f"reprovision:{server.id}")
        client.server_id = server.id
        client.is_active = True
        return client

    monkeypatch.setattr(service, "get_user_client", fake_get_user_client)
    monkeypatch.setattr(service, "_select_server_for_existing_client", fake_select_server)
    monkeypatch.setattr(service, "_reprovision_client", fake_reprovision)

    result = await service.create_client(user_id=10)
    assert result is existing
    assert existing.server_id == 8
    assert existing.is_active is True
    assert calls == ["reprovision:8"]
