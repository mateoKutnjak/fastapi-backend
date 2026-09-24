import uuid
from datetime import UTC, datetime, timedelta

from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.v1.auth.authentication import UserContext
from app.api.v1.auth.models import (
    EmailVerificationToken,
    ForgotPasswordToken,
    OAuthAccount,
    Session,
)
from app.api.v1.auth.schemas import (
    ChangePasswordRequest,
    ResetPasswordRequest,
    SessionMetadata,
    SetPasswordRequest,
    TokenResponse,
)
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
    ConflictError,
    CurrentUserAlreadyHasPasswordError,
    CurrentUserHasNoPasswordError,
    ExpiredPasswordResetTokenError,
    ExpiredVerificationTokenError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    InvalidOAuthTokenError,
    InvalidPasswordResetTokenError,
    InvalidRefreshTokenError,
    InvalidVerificationTokenError,
    OAuthEmailNotProvidedError,
    OAuthEmailNotVerifiedError,
    RoleNotFoundError,
    UserNotFoundError,
)
from app.core.exceptions.error_codes import ErrorCode
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


async def create_session_tokens(
    db: AsyncSession,
    user_id: uuid.UUID,
    metadata: SessionMetadata,
    expires_delta: int | None = None,
    absolute_expires_delta: int | None = None,
) -> TokenResponse:
    raw_refresh_token, session = await create_refresh_token(
        db,
        user_id,
        metadata,
        settings.refresh_token_expire_minutes
        if expires_delta is None
        else expires_delta,
        settings.absolute_refresh_token_expire_minutes
        if absolute_expires_delta is None
        else absolute_expires_delta,
    )
    access_token = create_access_token(subject=user_id, session_id=session.id)

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh_token)


async def create_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    metadata: SessionMetadata,
    expires_delta: int,
    absolute_expires_delta: int,
) -> tuple[str, Session]:
    raw_token = generate_random_token()

    token_hash = hash_string(raw_token)

    session = Session(
        user_id=user_id,
        refresh_token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=expires_delta),
        absolute_expires_at=datetime.now(UTC)
        + timedelta(minutes=absolute_expires_delta),
        device_name=metadata.device_name,
        device_id=metadata.device_id,
        user_agent=metadata.user_agent,
        ip_address=metadata.ip_address,
    )

    db.add(session)
    await db.flush()

    return raw_token, session


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
    await db.flush()

    return raw_token


async def register_user(
    body: UserCreate,
    db: AsyncSession,
    metadata: SessionMetadata,
) -> tuple[TokenResponse, str]:
    conflict_fields = {}

    try:
        if await get_user_by_email(db, body.email):
            conflict_fields.update({"email": ErrorCode.EMAIL_ALREADY_EXISTS.value})

    except UserNotFoundError:
        pass

    try:
        if await get_user_by_username(db, body.username):
            conflict_fields.update(
                {"username": ErrorCode.USERNAME_ALREADY_EXISTS.value}
            )

    except UserNotFoundError:
        pass

    if conflict_fields:
        raise ConflictError(conflict_fields)

    user = await create_user(db, body)

    raw_email_verification_token = await create_verification_token(db, user.id)
    token_response = await create_session_tokens(db, user.id, metadata=metadata)

    await db.commit()

    return token_response, raw_email_verification_token


async def login_user(
    db: AsyncSession, identifier: str, password: str, metadata: SessionMetadata
) -> TokenResponse:
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

    return await create_session_tokens(db, user.id, metadata)


async def logout_user_from_one_device(
    db: AsyncSession,
    user_context: UserContext,
) -> None:
    await db.execute(
        update(Session)
        .where(
            Session.id == user_context.session.id,
            Session.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


async def logout_user_from_all_devices(
    db: AsyncSession,
    user_context: UserContext,
) -> None:
    await db.execute(
        update(Session)
        .where(
            Session.user_id == user_context.user.id,
            Session.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


async def refresh_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenResponse:

    session = await db.scalar(
        select(Session)
        .where(Session.refresh_token_hash == hash_string(refresh_token))
        .with_for_update()
    )

    now = datetime.now(UTC)

    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or session.absolute_expires_at <= now
    ):
        raise InvalidRefreshTokenError()

    new_refresh_token = generate_random_token()

    session.refresh_token_hash = hash_string(new_refresh_token)
    session.expires_at = min(
        now + timedelta(minutes=settings.refresh_token_expire_minutes),
        session.absolute_expires_at,
    )

    token_response = TokenResponse(
        access_token=create_access_token(session.user_id, session.id),
        refresh_token=new_refresh_token,
    )

    await db.commit()

    return token_response


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

    # Revoke all active sessions for the user to force re-authentication
    await db.execute(
        update(Session)
        .where(
            Session.user_id == user.id,
            Session.revoked_at.is_(None),
        )
        .values(
            revoked_at=datetime.now(UTC),
        )
    )

    await db.commit()


async def change_password(
    db: AsyncSession, user_context: UserContext, body: ChangePasswordRequest
) -> None:
    if not user_context.user.password_hash:
        raise CurrentUserHasNoPasswordError()

    if not verify_password(body.current_password, user_context.user.password_hash):
        raise InvalidCurrentPasswordError()

    user_context.user.password_hash = hash_password(body.new_password)

    # Revoke all other active sessions for the user to force re-authentication
    await db.execute(
        update(Session)
        .where(
            Session.user_id == user_context.user.id,
            Session.id != user_context.session.id,
            Session.revoked_at.is_(None),
        )
        .values(
            revoked_at=datetime.now(UTC),
        )
    )
    await db.commit()


async def set_password(
    db: AsyncSession, user_context: UserContext, body: SetPasswordRequest
) -> None:
    if user_context.user.password_hash:
        raise CurrentUserAlreadyHasPasswordError()

    user_context.user.password_hash = hash_password(body.new_password)

    # Revoke all other active sessions for the user to force re-authentication
    await db.execute(
        update(Session)
        .where(
            Session.user_id == user_context.user.id,
            Session.id != user_context.session.id,
            Session.revoked_at.is_(None),
        )
        .values(
            revoked_at=datetime.now(UTC),
        )
    )
    await db.commit()


async def google_sign_in(
    db: AsyncSession, token_received, metadata: SessionMetadata
) -> TokenResponse:

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

    return await create_session_tokens(db, user.id, metadata)
