import logging
import uuid

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.api.v1.users.models import Role, User
from app.api.v1.users.schemas import UserCreate
from app.config import settings
from app.core.db import AsyncSession
from app.core.exceptions.domain_exceptions import UserNotFoundError
from app.core.images import validate_image
from app.core.security import hash_password
from app.core.storage import Storage, get_storage


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
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        raise UserNotFoundError()
    return user


async def delete_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise UserNotFoundError()

    avatar_key = user.avatar_key

    await db.delete(user)
    await db.commit()

    if avatar_key:
        try:
            storage = get_storage()
            await storage.delete(avatar_key)
        except Exception as e:
            logging.exception(
                "Failed to delete avatar after database failure", exc_info=e
            )


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    default_role = await get_default_role(db)

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=default_role.id,
    )

    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def get_default_role(db: AsyncSession) -> Role:
    result = await db.execute(select(Role).where(Role.name == "user"))
    role = result.scalar_one_or_none()
    if role is None:
        raise ValueError("Default role 'user' not found — did you seed roles?")
    return role


async def update_user_avatar(
    db: AsyncSession, user_id: uuid.UUID, file: UploadFile
) -> User:

    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise UserNotFoundError()

    old_avatar_key = user.avatar_key

    data = await file.read(settings.max_user_avatar_bytes + 1)
    image_info = await run_in_threadpool(validate_image, data)

    storage: Storage = get_storage()
    new_avatar_key = await storage.save(
        file.filename,
        image_info.data,
        extension=image_info.extension,
        subfolder="avatars",
    )

    try:
        user.avatar_key = new_avatar_key
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception as e:
            logging.exception("Failed to commit user avatar update", exc_info=e)
        finally:
            try:
                await storage.delete(new_avatar_key)
            except Exception as e:
                logging.exception(
                    "Failed to delete new avatar after database failure", exc_info=e
                )

        raise

    if old_avatar_key:
        try:
            await storage.delete(old_avatar_key)
        except Exception:
            logging.exception("Failed to delete previous avatar")

    return user


async def delete_user_avatar(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise UserNotFoundError()

    avatar_key = user.avatar_key
    user.avatar_key = None

    try:
        await db.commit()
    except Exception as e:
        try:
            await db.rollback()
        except Exception as e:
            logging.exception(
                "Failed to rollback after avatar delete failure",
                exc_info=e,
            )
        raise e

    if avatar_key:
        try:
            storage = get_storage()
            await storage.delete(avatar_key)
        except Exception as e:
            logging.exception("Failed to delete user avatar from storage", exc_info=e)

    return user
