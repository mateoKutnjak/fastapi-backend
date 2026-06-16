import uuid

from sqlalchemy import select

from app.core.db import AsyncSession
from app.core.security import hash_password
from app.api.v1.users.models import Role, User
from app.api.v1.users.schemas import UserCreate


async def get_all_users(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate):
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
