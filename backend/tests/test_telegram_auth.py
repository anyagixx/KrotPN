import hashlib
import hmac
import time

from app.users import router as users_router_module


class StubUserService:
    def __init__(self, session):
        self.session = session

    async def create_user_telegram(self, data, referral_code=None):
        class User:
            id = 123
            referred_by_id = None
            is_active = True

        return User()


def _make_telegram_hash(bot_token: str, payload: dict[str, str]) -> str:
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def test_telegram_auth_rejects_unsigned_requests(build_client, monkeypatch):
    monkeypatch.setattr(users_router_module, "UserService", StubUserService)

    async def noop_initialize(*args, **kwargs):
        return None

    monkeypatch.setattr(users_router_module, "_initialize_new_user_resources", noop_initialize)
    monkeypatch.setattr(users_router_module.settings, "telegram_bot_token", "bot-secret")

    client = build_client(users_router_module.router, users_router_module.limiter)

    response = client.post(
        "/api/auth/telegram",
        json={
            "telegram_id": 42,
            "telegram_username": "intruder",
            "name": "Intruder",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Telegram authentication data"


def test_telegram_auth_accepts_valid_signed_payload(build_client, monkeypatch):
    monkeypatch.setattr(users_router_module, "UserService", StubUserService)

    async def noop_initialize(*args, **kwargs):
        return None

    monkeypatch.setattr(users_router_module, "_initialize_new_user_resources", noop_initialize)
    monkeypatch.setattr(users_router_module.settings, "telegram_bot_token", "bot-secret")

    client = build_client(users_router_module.router, users_router_module.limiter)
    auth_date = int(time.time())

    auth_payload = {
        "auth_date": str(auth_date),
        "first_name": "Valid User",
        "id": "42",
        "username": "valid_user",
    }
    auth_hash = _make_telegram_hash(users_router_module.settings.telegram_bot_token, auth_payload)

    response = client.post(
        "/api/auth/telegram",
        json={
            "telegram_id": 42,
            "telegram_username": "valid_user",
            "name": "Valid User",
            "auth_date": auth_date,
            "hash": auth_hash,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
