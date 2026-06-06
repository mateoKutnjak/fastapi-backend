import uuid
from typing import Annotated

from fastapi import Body, HTTPException, status
from fastapi.params import Depends

from app.auth.schemas import TokenResponse
from app.core.db import AsyncSession, get_db
from app.core.exceptions import FieldConflictException
from app.core.security import TokenType, create_token, verify_password, verify_token
from app.users.schemas import UserCreate
from app.users.services import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
)


def generate_tokens(subject: uuid.UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_token(subject, TokenType.ACCESS),
        refresh_token=create_token(subject, TokenType.REFRESH),
    )


async def register_user(
    body: Annotated[UserCreate, Body()], db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    if await get_user_by_username(db, body.username):
        raise FieldConflictException(
            field="username",
            message="Username already exists",
        )

    if await get_user_by_email(db, body.email):
        raise FieldConflictException(
            field="email",
            message="Email already exists",
        )

    user = await create_user(db, body)
    return generate_tokens(user.id)


async def login_user(
    db: Annotated[AsyncSession, Depends(get_db)], email: str, password: str
) -> TokenResponse:
    user = await get_user_by_email(db, email)

    if not user or not verify_password(password, user.password_hash):
        raise FieldConflictException(
            field="",
            message="Invalid email or password",
        )

    return generate_tokens(user.id)


async def refresh_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: str,
) -> TokenResponse:
    user_id = verify_token(refresh_token, TokenType.REFRESH)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return generate_tokens(user.id)
