import pytest
from sqlalchemy import select

from app.api.v1.users.constants import RoleEnum
from app.api.v1.users.models import Role, User
from app.core.db import AsyncSession


@pytest.mark.anyio
async def test_user_email_normalized_to_lowercase_on_construction(
    db_session: AsyncSession,
):
    role = await db_session.scalar(select(Role).where(Role.name == RoleEnum.USER))

    user = User(
        email="Test@GMAIL.com",
        password_hash=None,
        is_verified=True,
        role_id=role.id,
    )

    # normalization should happen immediately on assignment, before any DB round-trip
    assert user.email == "test@gmail.com"


@pytest.mark.anyio
async def test_user_email_normalized_to_lowercase_after_persisting(
    db_session: AsyncSession,
):
    role = await db_session.scalar(select(Role).where(Role.name == RoleEnum.USER))

    user = User(
        email="MixedCase@Example.COM",
        password_hash=None,
        is_verified=True,
        role_id=role.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    assert user.email == "mixedcase@example.com"

    # confirm it's actually lowercase in the DB, not just in the Python object
    stored = await db_session.scalar(select(User).where(User.id == user.id))
    assert stored.email == "mixedcase@example.com"


@pytest.mark.anyio
async def test_user_email_normalized_on_reassignment(db_session: AsyncSession):
    role = await db_session.scalar(select(Role).where(Role.name == RoleEnum.USER))

    user = User(
        email="original@example.com",
        password_hash=None,
        is_verified=True,
        role_id=role.id,
    )
    db_session.add(user)
    await db_session.flush()

    user.email = "Changed@EXAMPLE.com"
    assert user.email == "changed@example.com"

    await db_session.flush()
    await db_session.refresh(user)
    assert user.email == "changed@example.com"
