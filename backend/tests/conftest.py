from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from starlette.testclient import TestClient

from app.core.database import get_session, import_all_models
from app.core.security import create_access_token
from app.users.models import User, UserRole

import_all_models()


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


@pytest.fixture
def app():
    """Create a test FastAPI app with common routers."""
    from app.users.router import router as users_router
    from app.admin.router import router as admin_router
    from app.vpn.router import router as vpn_router

    test_app = FastAPI()
    test_app.include_router(users_router)
    test_app.include_router(admin_router)
    test_app.include_router(vpn_router)
    return test_app


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """SQLite in-memory session for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a regular test user."""
    user = User(
        email="testuser@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    admin = User(
        email="admin@example.com",
        password_hash="hashed",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


@pytest.fixture
def test_user_headers(test_user: User) -> dict[str, str]:
    """Auth headers for a regular user."""
    token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_admin_headers(test_admin: User) -> dict[str, str]:
    """Auth headers for an admin user."""
    token = create_access_token(subject=str(test_admin.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(app: FastAPI, db_session: AsyncSession) -> TestClient:
    """TestClient with dependency overrides."""
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)
