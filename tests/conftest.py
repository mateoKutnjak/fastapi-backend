import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.users.models import Role, User
from app.config import Settings
from app.core.db import Base, get_db
from app.core.seed import seed_db
from app.main import app

API_VERSION = "/api/v1"

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
def test_session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="rollback_only",
    )


@pytest_asyncio.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with TestSessionLocal() as db:
        await seed_db(db)

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
    await conn.begin_nested()

    TestSessionLocal = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async with TestSessionLocal() as session:
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


@pytest_asyncio.fixture(scope="function")
async def registered_user_with_role(
    client: AsyncClient,
    db_session: AsyncSession,
):
    async def _register(role_name: str):

        unique_id = uuid.uuid4().hex[:8]

        username = f"testuser_{unique_id}"
        email = f"test_{unique_id}@example.com"
        password = "testpassword123"

        user_data = await register_test_user(
            client, username=username, email=email, password=password
        )

        role = await db_session.scalar(select(Role).where(Role.name == role_name))

        user = await db_session.get(User, uuid.UUID(user_data["id"]))
        user.role_id = role.id

        await db_session.flush()

        return {**user_data}

    return _register


async def register_test_user(
    client: AsyncClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> dict:
    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, f"Failed to create user: {response.text}"

    user = await client.get(
        f"{API_VERSION}/users/me",
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
