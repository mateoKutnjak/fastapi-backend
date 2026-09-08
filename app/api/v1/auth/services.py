import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.api.v1.auth.schemas import TokenResponse
from app.api.v1.users.models import EmailVerificationToken, User
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.services import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
)
from app.config import settings
from app.core.db import AsyncSession
from app.core.exceptions.domain_exceptions import (
    ExpiredTokenError,
    ExpiredVerificationTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    InvalidVerificationTokenError,
    UserNotFoundError,
    ValidationError,
)
from app.core.security import (
    TokenType,
    create_token,
    hash_verification_token,
    verify_password,
    verify_token,
)


def generate_tokens(subject: uuid.UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_token(subject, TokenType.ACCESS),
        refresh_token=create_token(subject, TokenType.REFRESH),
    )


async def create_verification_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    raw_token = secrets.token_urlsafe(32)

    token_hash = hash_verification_token(raw_token)

    verification_token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC)
        + timedelta(seconds=settings.email_verification_token_expire_seconds),
    )

    db.add(verification_token)
    await db.commit()

    return raw_token


async def register_user(
    body: UserCreate,
    db: AsyncSession,
) -> tuple[TokenResponse, str]:
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

    raw_token = await create_verification_token(db, user.id)
    token_response = generate_tokens(user.id)

    return token_response, raw_token


async def login_user(db: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await get_user_by_email(db, email)

    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()

    return generate_tokens(user.id)


async def refresh_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenResponse:
    try:
        user_id = verify_token(refresh_token, TokenType.REFRESH)
    except (InvalidTokenError, ExpiredTokenError) as e:
        raise InvalidRefreshTokenError() from e

    user = await get_user_by_id(db, user_id)

    if user is None:
        raise UserNotFoundError()

    return generate_tokens(user.id)


async def verify_email(db: AsyncSession, raw_token: str) -> None:

    token_hash = hash_verification_token(raw_token)

    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
    )

    token = result.scalar_one_or_none()

    if not token:
        raise InvalidVerificationTokenError()

    if token.expires_at < datetime.now(UTC):
        raise ExpiredVerificationTokenError()

    await db.execute(
        update(User).where(User.id == token.user_id).values(is_verified=True)
    )
    await db.delete(token)
    await db.commit()
