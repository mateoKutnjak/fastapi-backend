from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.users.models import Role, User
from app.core.db import AsyncSession, get_db
from app.core.exceptions.http_exceptions import ForbiddenException, UnauthorizedException
from app.core.security import TokenType, verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # * Override the default behavior of OAuth2PasswordBearer to not raise an exception
    # * if no token is provided. Without this line the 401 exception would be raised with
    # * "details": "Not authenticated"}.

    if token is None:
        raise UnauthorizedException()

    try:
        user_id = verify_token(token, TokenType.ACCESS)
    except UnauthorizedException:
        # * We catch the exception which has a message and status code and
        # * raise a new one to avoid exposing the message to potentinal attackers.
        raise UnauthorizedException()

    # * Fetch role with user
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedException()

    return user


def require_permission(permission: str):
    async def permission_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        permissions = [perm.name for perm in current_user.role.permissions]

        if permission not in permissions:
            raise ForbiddenException()
        return current_user

    return permission_dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
