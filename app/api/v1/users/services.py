import uuid

from sqlalchemy import select

from app.api.v1.users.models import Role, User
from app.api.v1.users.schemas import UserCreate
from app.core.db import AsyncSession
from app.core.exceptions.domain_exceptions import UserNotFoundError
from app.core.security import hash_password


async def get_all_users(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise UserNotFoundError()
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User:
    user = await db.scalar(select(User).where(User.username == username))
    if user is None:
        raise UserNotFoundError()
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        raise UserNotFoundError()
    return user


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    default_role = await get_default_role(db)

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=default_role.id,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_default_role(db: AsyncSession) -> Role:
    result = await db.execute(select(Role).where(Role.name == "user"))
    role = result.scalar_one_or_none()
    if role is None:
        raise ValueError("Default role 'user' not found — did you seed roles?")
    return role
