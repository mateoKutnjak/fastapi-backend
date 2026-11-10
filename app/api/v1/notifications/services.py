from sqlalchemy import select

from app.api.v1.auth.authentication import UserContext
from app.api.v1.notifications.models import PushNotificationToken
from app.core.db import AsyncSession
from app.core.exceptions.domain_exceptions import FCMTokenUpdateForbiddenError


async def register_push_token(
    db: AsyncSession, user_context: UserContext | None, token: str, fid: str
):
    existing_token = await db.execute(
        select(PushNotificationToken).where(
            PushNotificationToken.fid == fid,
        )
    )

    existing_token = existing_token.scalar_one_or_none()

    user_id = user_context.user.id if user_context else None

    if existing_token:
        if user_id is None and existing_token.user_id is not None:
            # ? Unathenticated user should not be able to update a token that belongs to another user  # noqa: E501
            raise FCMTokenUpdateForbiddenError()

        if (
            user_id is not None
            and existing_token.user_id is not None
            and existing_token.user_id != user_id
        ):
            # ? Authenticated user does not match the token user -> raise exception
            raise FCMTokenUpdateForbiddenError()

        existing_token.token = token
        existing_token.user_id = user_id
    else:
        device_push_token = PushNotificationToken(
            token=token,
            user_id=user_id,
            fid=fid,
        )

        db.add(device_push_token)

    await db.commit()


async def unlink_push_token(db: AsyncSession, user_context: UserContext, fid: str):
    device_push_token = await db.execute(
        select(PushNotificationToken).where(
            PushNotificationToken.fid == fid,
            PushNotificationToken.user_id == user_context.user.id,
        )
    )

    device_push_token = device_push_token.scalar_one_or_none()

    if device_push_token:
        device_push_token.user_id = None
        await db.commit()


async def delete_push_token(
    db: AsyncSession, user_context: UserContext | None, fid: str
):
    device_push_token = await db.execute(
        select(PushNotificationToken).where(
            PushNotificationToken.fid == fid,
        )
    )

    device_push_token = device_push_token.scalar_one_or_none()

    if device_push_token is None:
        return

    if device_push_token.user_id is not None and (
        user_context is None or device_push_token.user_id != user_context.user.id
    ):
        return

    await db.delete(device_push_token)
    await db.commit()
