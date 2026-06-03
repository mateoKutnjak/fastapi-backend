from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.core.db import Base, get_db
from app.main import app

# * Needed to use async fixtures in pytest
pytest_plugins = ["anyio"]

test_settings = Settings(_env_file=".env.test")


# * Needed to use async fixtures in pytest
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    return engine


@pytest_asyncio.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


# * Not defining scope means scope="function" (runs for each test)
# * After each test we roll back changes to keep the database clean for the next test
@pytest_asyncio.fixture
async def db_session(
    test_engine,
    setup_database,
) -> AsyncGenerator[AsyncSession]:
    conn = await test_engine.connect()
    trans = await conn.begin()

    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="rollback_only",
    )

    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
            await conn.close()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:

    async def override_get_db():
        yield db_session

    # * Replace DB session with test DB session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    return await register_test_user(client)


@pytest_asyncio.fixture
async def authorized_client(client: AsyncClient, registered_user: dict) -> AsyncClient:
    client.headers.update(auth_headers(registered_user["access_token"]))
    return client


async def register_test_user(
    client: AsyncClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> dict:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, f"Failed to create user: {response.text}"

    user = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert user.status_code == 200, f"Failed to get user: {user.text}"

    return {
        "id": user.json()["id"],
        "username": username,
        "email": email,
        "password": password,
        **response.json(),
    }


async def login_test_user(
    client: AsyncClient,
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> dict:
    response = await client.post(
        "/api/auth/token",
        data={
            "username": email,
            "password": password,
        },
    )
    assert response.status_code == 200, f"Failed to login: {response.text}"

    return {
        "username": email,
        "email": email,
        "password": password,
        **response.json(),
    }


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
