from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.testclient import TestClient

from app.core.database import get_session


class DummySession:
    pass


@pytest.fixture
def dummy_session() -> DummySession:
    return DummySession()


@pytest.fixture
def build_client(dummy_session: DummySession):
    def _build(router, limiter) -> TestClient:
        app = FastAPI()
        app.include_router(router)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        async def override_session() -> AsyncGenerator[DummySession, None]:
            yield dummy_session

        app.dependency_overrides[get_session] = override_session
        return TestClient(app)

    return _build
