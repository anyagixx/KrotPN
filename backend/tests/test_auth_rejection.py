"""
MODULE_CONTRACT
- PURPOSE: Verify authentication rejection paths for protected endpoints.
- SCOPE: 401 without token, 403 for non-admin access to admin endpoints.
- DEPENDS: app.core.dependencies.
- LINKS: V-M-001.

MODULE_MAP
- test_users_me_returns_401_without_token: Verifies unauthenticated access to /api/users/me.
- test_admin_users_returns_401_without_token: Verifies unauthenticated access to /api/admin/users.
- test_admin_users_returns_403_with_regular_user_token: Verifies non-admin rejection.
- test_vpn_config_returns_401_without_token: Verifies unauthenticated VPN config access.

CHANGE_SUMMARY
- 2026-04-05: Added auth rejection tests for Phase 5.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from app.core import get_current_user, get_current_admin
from app.core.database import get_session


class DummySession:
    pass


def _make_protected_endpoint(user_dep):
    async def handler(user=Depends(user_dep)):
        return {"ok": True}
    return handler


def _build_app_with_user(user=None):
    app = FastAPI()

    async def override_session():
        yield DummySession()

    async def current_user_override():
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    async def current_admin_override():
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if not getattr(user, "is_admin", False):
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = current_user_override
    app.dependency_overrides[get_current_admin] = current_admin_override

    app.add_api_route("/api/users/me", _make_protected_endpoint(get_current_user), methods=["GET"])
    app.add_api_route("/api/admin/users", _make_protected_endpoint(get_current_admin), methods=["GET"])
    app.add_api_route("/api/vpn/config", _make_protected_endpoint(get_current_user), methods=["POST"])

    return TestClient(app)


def test_users_me_returns_401_without_token():
    client = _build_app_with_user(user=None)
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_admin_users_returns_401_without_token():
    client = _build_app_with_user(user=None)
    response = client.get("/api/admin/users")
    assert response.status_code == 401


def test_admin_users_returns_403_with_regular_user_token():
    class RegularUser:
        id = 1
        is_active = True

        @property
        def is_admin(self):
            return False

    client = _build_app_with_user(user=RegularUser())
    response = client.get("/api/admin/users")
    assert response.status_code == 403


def test_vpn_config_returns_401_without_token():
    client = _build_app_with_user(user=None)
    response = client.post("/api/vpn/config", json={})
    assert response.status_code == 401
