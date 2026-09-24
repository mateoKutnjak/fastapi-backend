from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.auth.models import Session
from app.api.v1.users.models import Role, User
from app.core.db import AsyncSession
from app.core.exceptions.domain_exceptions import (
    AuthenticationFailedError,
    ExpiredTokenError,
    InvalidTokenError,
)
from app.core.security import verify_access_token


@dataclass
class UserContext:
    user: User
    session: Session


async def authenticate_access_token(db: AsyncSession, token: str) -> UserContext:
    try:
        user_id, session_id = verify_access_token(token)
    except (InvalidTokenError, ExpiredTokenError) as e:
        # * We catch the exception which has a message and status code and
        # * raise a new one to avoid exposing the message to potentinal attackers.
        raise AuthenticationFailedError() from e

    session = await db.execute(
        select(Session).where(
            Session.id == session_id,  # Reference to specific access token session_id
            Session.user_id == user_id,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
            Session.absolute_expires_at > datetime.now(UTC),
        )
    )

    session = session.scalar_one_or_none()
    if session is None:
        # * No active session
        raise AuthenticationFailedError()

    # * Fetch role with user
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        # * User not found
        raise AuthenticationFailedError()

    return UserContext(user=user, session=session)
