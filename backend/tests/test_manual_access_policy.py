import asyncio
from datetime import datetime, timedelta

from app.billing.models import Subscription, SubscriptionStatus
from app.billing.service import BillingService
from app.users.service import UserService


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, execute_results=None):
        self._execute_results = list(execute_results or [])
        self.added = []
        self.flush_calls = 0
        self.refresh_calls = 0

    async def execute(self, query):
        del query
        if not self._execute_results:
            raise AssertionError("unexpected execute call")
        return _ScalarResult(self._execute_results.pop(0))

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = len(self.added)

    async def flush(self):
        self.flush_calls += 1

    async def refresh(self, obj):
        del obj
        self.refresh_calls += 1


def test_build_internal_user_email_normalizes_identity():
    service = UserService(FakeSession())

    assert service.build_internal_user_email("My Family Client") == "internal+my-family-client@local.krotpn"


def test_resolve_internal_user_reuses_existing_user():
    user = type(
        "UserStub",
        (),
        {
            "id": 42,
            "name": "Existing",
            "updated_at": None,
        },
    )()
    service = UserService(FakeSession())

    async def fake_get_by_email(email: str):
        assert email == "internal+family-phone@local.krotpn"
        return user

    service.get_by_email = fake_get_by_email  # type: ignore[method-assign]

    resolved = asyncio.run(service.resolve_internal_user("family phone"))

    assert resolved is user


def test_ensure_complimentary_access_reuses_active_subscription():
    existing = Subscription(
        id=7,
        user_id=10,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        is_complimentary=True,
        access_label="family",
    )
    session = FakeSession(execute_results=[existing])
    service = BillingService(session)

    subscription = asyncio.run(
        service.ensure_complimentary_access(
            10,
            access_label="family",
        )
    )

    assert subscription is existing
    assert session.added == []
    assert session.flush_calls == 0
    assert session.refresh_calls == 0


def test_ensure_complimentary_access_creates_subscription_when_missing():
    session = FakeSession(execute_results=[None, None])
    service = BillingService(session)

    subscription = asyncio.run(
        service.ensure_complimentary_access(
            11,
            access_label="family",
            duration_days=365,
        )
    )

    assert subscription.user_id == 11
    assert subscription.is_complimentary is True
    assert subscription.is_trial is False
    assert subscription.access_label == "family"
    assert session.flush_calls == 1
    assert session.refresh_calls == 1
