from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.users.models import Role, User
from app.core.db import AsyncSession, get_db
from app.core.security import TokenType, verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user_id = verify_token(token, TokenType.ACCESS)

    # * Fetch role with user
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    return user


def require_permission(permission: str):
    async def permission_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        permissions = [perm.name for perm in current_user.role.permissions]

        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return permission_dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
