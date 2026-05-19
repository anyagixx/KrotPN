"""
MODULE_CONTRACT
- PURPOSE: Verify billing webhook security and idempotent YooKassa processing.
- SCOPE: Router-level invalid-signature rejection and BillingService idempotency behavior.
- DEPENDS: M-004 billing router/service, V-M-004 verification.
- LINKS: docs/modules/M-004.xml, docs/verification/V-M-004.xml.

MODULE_MAP
- test_yookassa_webhook_rejects_invalid_signature: Verifies the versioned webhook route rejects invalid signatures before service processing.
- test_process_yookassa_webhook_is_idempotent_for_succeeded: Verifies duplicate succeeded webhooks do not recreate subscriptions.

CHANGE_SUMMARY
- 2026-05-19: Aligned webhook route coverage with /api/v1 billing router prefix for Phase-28 debt closure.
"""

import hashlib
import hmac

import pytest

from app.billing import router as billing_router_module
from app.billing.models import Payment, PaymentProvider, PaymentStatus
from app.billing.service import BillingService


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, payment: Payment):
        self.payment = payment
        self.flushed = False

    async def execute(self, query):
        return _ScalarResult(self.payment)

    async def flush(self):
        self.flushed = True


class StubBillingService:
    def __init__(self, session):
        self.session = session
        self.called = False

    async def process_payment_webhook(self, provider, data):
        self.called = True
        return None


def _make_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_yookassa_webhook_rejects_invalid_signature(build_client, monkeypatch):
    service = StubBillingService(session=None)

    monkeypatch.setattr(billing_router_module, "BillingService", lambda session: service)
    monkeypatch.setattr(billing_router_module.yookassa_client, "secret_key", "webhook-secret")

    client = build_client(billing_router_module.router, object())

    response = client.post(
        "/api/v1/billing/webhooks/yookassa",
        json={"event": "payment.succeeded", "object": {"id": "pay_1", "status": "succeeded"}},
        headers={"X-Content-Signature": "invalid"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid signature"
    assert service.called is False


@pytest.mark.asyncio
async def test_process_yookassa_webhook_is_idempotent_for_succeeded(monkeypatch):
    payment = Payment(
        id=1,
        user_id=10,
        plan_id=7,
        provider=PaymentProvider.YOOKASSA,
        status=PaymentStatus.SUCCEEDED,
        external_id="pay_1",
        amount=199.0,
        currency="RUB",
    )
    session = FakeSession(payment)
    service = BillingService(session)

    async def fail_create_subscription(*args, **kwargs):
        raise AssertionError("duplicate webhook must not recreate subscription")

    monkeypatch.setattr(service, "create_subscription", fail_create_subscription)

    result = await service._process_yookassa_webhook(
        {
            "event": "payment.succeeded",
            "object": {
                "id": "pay_1",
                "status": "succeeded",
            },
        }
    )

    assert result is payment
    assert session.flushed is False
