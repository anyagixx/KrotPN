"""
MODULE_CONTRACT
- PURPOSE: Verify plan API payloads expose and accept device_limit so plan-bound device enforcement can be administered without DB-only workarounds.
- SCOPE: Public plan listing, admin plan listing, admin plan create and admin plan update at router level with dependency overrides.
- DEPENDS: M-001 dependency overrides, M-004 billing API schemas and router serialization.
- LINKS: V-M-004, V-M-021.

MODULE_MAP
- _build_client: Constructs a FastAPI client with billing routers and auth or DB overrides.
- test_list_plan_endpoints_expose_device_limit: Verifies public and admin plan listings include device_limit.
- test_admin_plan_create_and_update_accept_device_limit: Verifies admin create and update payloads pass device_limit through router logic.

CHANGE_SUMMARY
- 2026-03-27: Added router-level coverage for plan device_limit visibility and admin mutation support.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.billing import router as billing_router_module
from app.core import get_current_admin, get_current_user
from app.core.database import get_session


class DummySession:
    async def flush(self):
        return None


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(billing_router_module.router)
    app.include_router(billing_router_module.admin_router)

    async def override_session():
        yield DummySession()

    async def current_user_override():
        return SimpleNamespace(id=1, is_active=True)

    async def current_admin_override():
        return SimpleNamespace(id=99, is_active=True)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = current_user_override
    app.dependency_overrides[get_current_admin] = current_admin_override
    return TestClient(app)


class StubBillingService:
    created_payload: dict | None = None
    updated_plan: SimpleNamespace | None = None

    def __init__(self, session):
        self.session = session

    async def get_plans(self, active_only: bool = True):
        return [
            SimpleNamespace(
                id=7,
                name="Plus",
                description="Three-device plan",
                price=999.0,
                currency="RUB",
                duration_days=30,
                device_limit=3,
                features=json.dumps(["feature-a"]),
                is_popular=True,
                is_active=True,
                sort_order=0,
            )
        ]

    async def create_plan(self, data: dict):
        StubBillingService.created_payload = data
        return SimpleNamespace(id=11)

    async def get_plan(self, plan_id: int):
        plan = SimpleNamespace(
            id=plan_id,
            name="Base",
            description="Base plan",
            price=499.0,
            currency="RUB",
            duration_days=30,
            device_limit=1,
            features=json.dumps(["feature-a"]),
            is_popular=False,
            is_active=True,
            sort_order=0,
        )
        StubBillingService.updated_plan = plan
        return plan


def test_list_plan_endpoints_expose_device_limit(monkeypatch):
    monkeypatch.setattr(billing_router_module, "BillingService", StubBillingService)
    client = _build_client()

    public_response = client.get("/api/billing/plans")
    admin_response = client.get("/api/admin/billing/plans")

    assert public_response.status_code == 200
    assert public_response.json()[0]["device_limit"] == 3
    assert admin_response.status_code == 200
    assert admin_response.json()[0]["device_limit"] == 3


def test_admin_plan_create_and_update_accept_device_limit(monkeypatch):
    monkeypatch.setattr(billing_router_module, "BillingService", StubBillingService)
    client = _build_client()

    create_response = client.post(
        "/api/admin/billing/plans",
        json={
            "name": "Family",
            "description": "Family plan",
            "price": 1499,
            "currency": "RUB",
            "duration_days": 30,
            "device_limit": 5,
            "features": ["priority-support"],
            "is_popular": True,
            "sort_order": 1,
        },
    )
    update_response = client.put(
        "/api/admin/billing/plans/7",
        json={
            "device_limit": 4,
            "features": ["priority-support", "bonus"],
        },
    )

    assert create_response.status_code == 201
    assert StubBillingService.created_payload is not None
    assert StubBillingService.created_payload["device_limit"] == 5

    assert update_response.status_code == 200
    assert StubBillingService.updated_plan is not None
    assert StubBillingService.updated_plan.device_limit == 4
    assert json.loads(StubBillingService.updated_plan.features) == ["priority-support", "bonus"]
