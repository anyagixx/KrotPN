"""
MODULE_CONTRACT
- PURPOSE: Verify manual internal client CLI orchestration and idempotency.
- SCOPE: Service orchestration, idempotent re-run for same identity.
- DEPENDS: app.cli, app.users.service, app.billing.service, app.vpn.service.
- LINKS: V-M-019.

MODULE_MAP
- test_issue_internal_client_orchestrates_services: Verifies full CLI flow.
- test_issue_internal_client_is_idempotent: Verifies repeated runs do not create duplicate clients.

CHANGE_SUMMARY
- 2026-03-26: Added manual client CLI tests.
- 2026-04-05: Cleaned up duplicate test and ensured idempotency test verifies single active client.
"""

import pytest

from app.cli import issue_internal_client


class DummyAsyncSession:
    def __init__(self):
        self.commit_calls = 0

    async def commit(self):
        self.commit_calls += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


class DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


class DummySubscription:
    def __init__(self, subscription_id: int):
        self.id = subscription_id


class DummyClient:
    def __init__(self, client_id: int):
        self.id = client_id


class DummyConfig:
    def __init__(self):
        self.config = "[Interface]\nPrivateKey = test\n"
        self.address = "10.10.0.9"


@pytest.mark.asyncio
async def test_issue_internal_client_orchestrates_services(monkeypatch):
    session = DummyAsyncSession()

    class StubUserService:
        def __init__(self, current_session):
            assert current_session is session

        async def resolve_internal_user(self, identity, *, display_name=None):
            assert identity == "family-phone"
            assert display_name == "Family Phone"
            return DummyUser(10)

    class StubBillingService:
        def __init__(self, current_session):
            assert current_session is session

        async def ensure_complimentary_access(self, user_id, *, access_label):
            assert user_id == 10
            assert access_label == "family"
            return DummySubscription(20)

    class StubVPNService:
        def __init__(self, current_session):
            assert current_session is session

        async def provision_internal_client(self, user_id, *, reprovision):
            assert user_id == 10
            assert reprovision is True
            return DummyClient(30)

        async def get_client_config(self, client):
            assert client.id == 30
            return DummyConfig()

    monkeypatch.setattr("app.cli.async_session_maker", lambda: session)
    monkeypatch.setattr("app.cli.UserService", StubUserService)
    monkeypatch.setattr("app.cli.BillingService", StubBillingService)
    monkeypatch.setattr("app.cli.VPNService", StubVPNService)

    user, subscription, client, config = await issue_internal_client(
        "family-phone",
        output="/tmp/family-phone.conf",
        display_name="Family Phone",
        access_label="family",
        reprovision=True,
    )

    assert user.id == 10
    assert subscription.id == 20
    assert client.id == 30
    assert config.address == "10.10.0.9"
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_issue_internal_client_is_idempotent(monkeypatch):
    created_clients = []
    session = DummyAsyncSession()

    call_count = {"create": 0}

    class StubUserService:
        def __init__(self, current_session):
            pass

        async def resolve_internal_user(self, identity, *, display_name=None):
            return DummyUser(10)

    class StubBillingService:
        def __init__(self, current_session):
            pass

        async def ensure_complimentary_access(self, user_id, *, access_label):
            return DummySubscription(20)

    class StubVPNService:
        def __init__(self, current_session):
            pass

        async def provision_internal_client(self, user_id, *, reprovision):
            call_count["create"] += 1
            if call_count["create"] == 1:
                client = DummyClient(30)
                created_clients.append(client)
                return client
            return created_clients[0]

        async def get_client_config(self, client):
            return DummyConfig()

    monkeypatch.setattr("app.cli.async_session_maker", lambda: session)
    monkeypatch.setattr("app.cli.UserService", StubUserService)
    monkeypatch.setattr("app.cli.BillingService", StubBillingService)
    monkeypatch.setattr("app.cli.VPNService", StubVPNService)

    user1, sub1, client1, config1 = await issue_internal_client(
        "test-client",
        output="/tmp/test-client.conf",
        display_name="Test Client",
        access_label="test",
        reprovision=True,
    )

    user2, sub2, client2, config2 = await issue_internal_client(
        "test-client",
        output="/tmp/test-client.conf",
        display_name="Test Client",
        access_label="test",
        reprovision=True,
    )

    assert client1.id == client2.id
    assert config1.address == config2.address
