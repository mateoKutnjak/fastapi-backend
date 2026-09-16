import uuid
from datetime import UTC, datetime, timedelta

from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.api.v1.auth.models import (
    EmailVerificationToken,
    ForgotPasswordToken,
    OAuthAccount,
    RefreshToken,
)
from app.api.v1.auth.schemas import ResetPasswordRequest, TokenResponse
from app.api.v1.users.constants import DEFAULT_ROLE
from app.api.v1.users.models import Role, User
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
    AccountLinkingError,
    ExpiredPasswordResetTokenError,
    ExpiredTokenError,
    ExpiredVerificationTokenError,
    InvalidCredentialsError,
    InvalidOAuthTokenError,
    InvalidPasswordResetTokenError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    InvalidVerificationTokenError,
    OAuthEmailNotProvidedError,
    OAuthEmailNotVerifiedError,
    RoleNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    generate_random_token,
    hash_password,
    hash_string,
    verify_password,
)


async def get_role_by_name(db: AsyncSession, name: str):
    role = await db.scalar(select(Role).where(Role.name == name))

    if not role:
        raise RoleNotFoundError(name)

    return role


async def create_refresh_token(
    db: AsyncSession, user_id: uuid.UUID, expires_delta: int
) -> str:
    raw_token = generate_random_token()

    token_hash = hash_string(raw_token)

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=expires_delta),
    )

    db.add(refresh_token)
    await db.commit()

    return raw_token


async def verify_refresh_token(
    db: AsyncSession, raw_refresh_token: str
) -> tuple[str, uuid.UUID]:
    hashed_refresh_token = hash_string(raw_refresh_token)

    refresh_token_record = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hashed_refresh_token)
    )

    if not refresh_token_record:
        raise InvalidRefreshTokenError()

    if refresh_token_record.expires_at < datetime.now(UTC):
        raise ExpiredTokenError()

    await db.delete(refresh_token_record)

    new_refresh_token = generate_random_token()

    new_refresh_token_record = RefreshToken(
        user_id=refresh_token_record.user_id,
        token_hash=hash_string(new_refresh_token),
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.refresh_token_expire_minutes),
    )

    db.add(new_refresh_token_record)
    await db.commit()

    return new_refresh_token, refresh_token_record.user_id


async def create_verification_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    raw_token = generate_random_token()

    token_hash = hash_string(raw_token)

    verification_token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.email_verification_token_expire_minutes),
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

    raw_email_verification_token = await create_verification_token(db, user.id)
    token_response = TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=await create_refresh_token(
            db, user.id, settings.refresh_token_expire_minutes
        ),
    )

    return token_response, raw_email_verification_token


async def login_user(db: AsyncSession, identifier: str, password: str) -> TokenResponse:
    try:
        if identifier.count("@") > 0:
            user = await get_user_by_email(db, identifier)
        else:
            user = await get_user_by_username(db, identifier)
    except UserNotFoundError as e:
        # Avoid leaking whether the identifier exists
        raise InvalidCredentialsError() from e

    # For users who registered via OAuth and do not have a password set
    if user.password_hash is None:
        raise InvalidCredentialsError()

    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=await create_refresh_token(
            db, user.id, settings.refresh_token_expire_minutes
        ),
    )


async def logout_user_from_one_device(
    db: AsyncSession,
    refresh_token: str,
) -> None:
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.token_hash == hash_string(refresh_token)
        )
    )
    await db.commit()


async def logout_user_from_all_devices(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()


async def refresh_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenResponse:
    try:
        new_refresh_token, user_id = await verify_refresh_token(db, refresh_token)
    except (InvalidTokenError, ExpiredTokenError) as e:
        raise InvalidRefreshTokenError() from e

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=new_refresh_token,
    )


async def verify_email(db: AsyncSession, raw_token: str) -> None:

    token_hash = hash_string(raw_token)

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


async def forgot_password(db: AsyncSession, email: str) -> str | None:
    raw_token = generate_random_token()

    token_hash = hash_string(raw_token)

    try:
        user = await get_user_by_email(db, email)
    except UserNotFoundError:
        # Intentionally ignore exception to not reveal existance of the email
        return None

    if user:
        password_reset_token = ForgotPasswordToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )

        db.add(password_reset_token)
        await db.commit()

    return raw_token


async def reset_password(db: AsyncSession, body: ResetPasswordRequest) -> None:
    token_hash = hash_string(body.token)

    result = await db.execute(
        select(ForgotPasswordToken).where(ForgotPasswordToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if not token:
        raise InvalidPasswordResetTokenError()

    if token.expires_at < datetime.now(UTC):
        raise ExpiredPasswordResetTokenError()

    user = await get_user_by_id(db, token.user_id)

    user.password_hash = hash_password(body.new_password)
    await db.delete(token)

    # Delete all refresh tokens associated with the user to force re-authentication
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))

    await db.commit()


async def google_sign_in(db: AsyncSession, token_received) -> TokenResponse:

    try:
        payload = id_token.verify_oauth2_token(
            token_received,
            requests.Request(),
            settings.google_client_id,
        )
    except ValueError as e:
        raise InvalidOAuthTokenError() from e

    # Sometimes payload does not include the email field, so we reject that
    if payload.get("email") is None:
        raise OAuthEmailNotProvidedError()

    # If the email is not verified or is missing, raise an error
    if not payload.get("email_verified"):
        raise OAuthEmailNotVerifiedError()

    sub = payload["sub"]
    email = payload.get("email").lower() if payload.get("email") else None
    email_verified = payload.get("email_verified", False)

    # Fetch the OAuthAccount if it exists
    o_auth_account = await db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == sub,
        )
    )

    if o_auth_account:
        # Update email if it has changed (and if it not ommitted from payload)
        o_auth_account.email = email if email else o_auth_account.email
        # Fetch the associated user from the database
        user = await db.get(User, o_auth_account.user_id)
        # Here we proceed with the login flow for the existing user
    else:
        existing_user = await db.scalar(select(User).where(User.email == email))

        if existing_user:
            # If OAuthAccount does not exist, we link it to the existing user
            user = existing_user
        else:
            role = await get_role_by_name(db, DEFAULT_ROLE)

            # If no existing user is found, we create a new user
            user = User(
                email=email,
                password_hash=None,
                is_verified=email_verified,
                role_id=role.id,
            )
            db.add(user)
            await db.flush()

        # Create the OAuthAccount and link it to the user
        o_auth_account = OAuthAccount(
            provider="google",
            provider_user_id=sub,
            email=email,
            user_id=user.id,
        )

        db.add(o_auth_account)

    try:
        # Attempt to commit the transaction to the database
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise AccountLinkingError() from e

    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=await create_refresh_token(
            db, user.id, settings.refresh_token_expire_minutes
        ),
    )
