from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin import router as admin_router_module
from app.core import get_current_admin
from app.core.database import get_session


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class DummySession:
    def __init__(self, values):
        self._values = iter(values)

    async def execute(self, statement):
        del statement
        return _ScalarResult(next(self._values))


def _build_client(session: DummySession) -> TestClient:
    app = FastAPI()
    app.include_router(admin_router_module.router)

    async def override_session():
        yield session

    async def current_admin_override():
        class Admin:
            id = 1
            is_active = True

        return Admin()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_admin] = current_admin_override
    return TestClient(app)


def test_admin_stats_exposes_route_aware_summary(monkeypatch):
    monkeypatch.setattr(
        admin_router_module.policy_dns_observer,
        "get_active_bindings",
        lambda: [object(), object()],
    )
    session = DummySession(
        [
            120,   # total_users
            17,    # new_users_month
            42,    # active_subs
            5,     # trial_subs
            12500, # revenue_month
            95000, # total_revenue
            34,    # active_vpn_clients
            2,     # online_servers
            6,     # active_nodes
            4,     # online_nodes
            3,     # active_routes
            1,     # default_routes
            7,     # active_domain_rules
            9,     # active_cidr_rules
        ]
    )
    client = _build_client(session)

    response = client.get("/api/admin/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["vpn"]["online_servers"] == 2
    assert body["vpn"]["online_servers_source"] == "legacy_vpn_server"
    assert body["routing"] == {
        "online_nodes": 4,
        "active_nodes": 6,
        "active_routes": 3,
        "default_routes": 1,
        "domain_rules_active": 7,
        "cidr_rules_active": 9,
        "dns_bindings_active": 2,
        "policy_mode": "domain_first_with_ru_fallback",
    }
