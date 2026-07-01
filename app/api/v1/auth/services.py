import uuid
from typing import Annotated

from fastapi import Body
from fastapi.params import Depends

from app.api.v1.auth.schemas import TokenResponse
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.services import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
)
from app.core.db import AsyncSession, get_db
from app.core.exceptions.domain_exceptions import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserNotFoundError,
    ValidationError,
)
from app.core.security import TokenType, create_token, verify_password, verify_token


def generate_tokens(subject: uuid.UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_token(subject, TokenType.ACCESS),
        refresh_token=create_token(subject, TokenType.REFRESH),
    )


async def register_user(
    body: Annotated[UserCreate, Body()], db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    conflict_fields = {}

    try:
        if await get_user_by_email(db, body.email):
            conflict_fields.update({"email": "Email already exists"})

    except UserNotFoundError:
        pass

    try:
        if await get_user_by_username(db, body.username):
            conflict_fields.update({"username": "Username already exists"})

    except UserNotFoundError:
        pass

    if conflict_fields:
        raise ValidationError(conflict_fields)

    user = await create_user(db, body)
    return generate_tokens(user.id)


async def login_user(
    db: Annotated[AsyncSession, Depends(get_db)], email: str, password: str
) -> TokenResponse:
    user = await get_user_by_email(db, email)

    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()

    return generate_tokens(user.id)


async def refresh_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: str,
) -> TokenResponse:
    try:
        user_id = verify_token(refresh_token, TokenType.REFRESH)
    except Exception:
        raise InvalidRefreshTokenError()

    user = await get_user_by_id(db, user_id)

    if user is None:
        raise UserNotFoundError()

    return generate_tokens(user.id)
