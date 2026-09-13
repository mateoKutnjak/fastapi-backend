import datetime
import uuid
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.users.constants import DEFAULT_ROLE, RoleEnum
from app.api.v1.users.models import (
    EmailVerificationToken,
    ForgotPasswordToken,
    OAuthAccount,
    Role,
    User,
)
from app.core.db import AsyncSession
from app.core.security import TokenType, create_token, hash_string
from tests.conftest import API_VERSION


def make_payload(**overrides) -> dict:
    payload = {
        "sub": "google-sub-" + uuid.uuid4().hex[:12],
        "email": f"test_{uuid.uuid4().hex[:8]}@gmail.com",
        "email_verified": True,
        "aud": "test-client-id",
        "iss": "accounts.google.com",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_register_user_validation_error(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": "testuser",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "email" in response.text
    assert "password" in response.text


@pytest.mark.asyncio
async def test_register_user_duplicate_email(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": "newuser",
            "email": user["email"],
            "password": "newpassword123",
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_409_CONFLICT
    assert data["error"]["status_code"] == status.HTTP_409_CONFLICT
    assert data["error"]["detail"] == "Conflict"
    assert data["error"]["fields"]["email"] == "Email already exists"


@pytest.mark.asyncio
async def test_register_user_duplicate_username(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": user["username"],
            "email": "newemail@example.com",
            "password": "newpassword123",
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_409_CONFLICT
    assert data["error"]["status_code"] == status.HTTP_409_CONFLICT
    assert data["error"]["detail"] == "Conflict"
    assert len(data["error"]["fields"]) == 1
    assert data["error"]["fields"]["username"] == "Username already exists"


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_login_token_user_with_email_invalid_credentials(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/token",
        data={
            "username": user["email"],
            "password": "wrongpassword",
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_login_token_user_with_username_invalid_credentials(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/token",
        data={
            "username": user["username"],
            "password": "wrongpassword",
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_login_token_user_with_email_success(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/token",
        data={
            "username": user["email"],
            "password": user["password"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_login_token_user_with_username_success(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/token",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_login_token_non_existing_user(
    client: AsyncClient, registered_user_with_role: dict
):
    response = await client.post(
        f"{API_VERSION}/auth/token",
        data={
            "username": "nonexistinguser",
            "password": "somepassword",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["detail"] == "Not found"


@pytest.mark.asyncio
async def test_login_body_user_with_email_invalid_credentials(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/login",
        json={
            "identifier": user["email"],
            "password": "wrongpassword",
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_login_body_user_with_username_invalid_credentials(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/login",
        json={
            "identifier": user["username"],
            "password": "wrongpassword",
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_login_body_user_with_email_success(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/login",
        json={
            "identifier": user["email"],
            "password": user["password"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_login_body_user_with_username_success(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/login",
        json={
            "identifier": user["username"],
            "password": user["password"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_login_body_non_existing_user(
    client: AsyncClient, registered_user_with_role: dict
):
    response = await client.post(
        f"{API_VERSION}/auth/login",
        json={
            "identifier": "nonexistinguser",
            "password": "somepassword",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["detail"] == "Not found"


@pytest.mark.asyncio
async def test_expired_access_token(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    expired_access_token = create_token(user["id"], TokenType.ACCESS, expires_delta=-5)

    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {expired_access_token}"},
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["status_code"] == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_success(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={
            "refresh_token": user["refresh_token"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_refresh_token_invalid_token(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={
            "refresh_token": "invalidtoken",
        },
    )
    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["status_code"] == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_expired_token(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    expired_refresh_token = create_token(
        user["id"], TokenType.REFRESH, expires_delta=-5
    )

    response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={
            "refresh_token": expired_refresh_token,
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["status_code"] == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_verify_email_success(
    client: AsyncClient,
    registered_user_with_role,
    mock_send_verification_email,
    db_session,
):
    user = await registered_user_with_role("user")

    _, raw_token = mock_send_verification_email.call_args.args

    response = await client.get(
        f"{API_VERSION}/auth/verify",
        params={"token": raw_token},
    )

    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["detail"] == "Email verified successfully"

    db_user = await db_session.get(User, user["id"])
    await db_session.refresh(db_user)

    assert db_user.is_verified is True

    db_email_verification_token = await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_string(raw_token)
        )
    )
    db_email_verification_token = db_email_verification_token.scalar_one_or_none()
    assert db_email_verification_token is None


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    response = await client.get(
        f"{API_VERSION}/auth/verify",
        params={"token": "not-a-real-token"},
    )

    data = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert data["error"]["detail"] == "Invalid verification token"


@pytest.mark.asyncio
async def test_verify_email_expired_token(
    client: AsyncClient,
    registered_user_with_role,
    mock_send_verification_email,
    db_session: AsyncSession,
):
    await registered_user_with_role("user")

    _, raw_token = mock_send_verification_email.call_args.args
    token_hash = hash_string(raw_token)

    result = await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
    )
    token_row = result.scalar_one()
    token_row.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        seconds=1
    )
    await db_session.flush()

    response = await client.get(
        f"{API_VERSION}/auth/verify",
        params={"token": raw_token},
    )

    data = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert data["error"]["detail"] == "Expired verification token"


@pytest.mark.anyio
async def test_google_sign_in_creates_new_user(
    client: AsyncClient, db_session: AsyncSession
):
    payload = make_payload()

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        response = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "fake-token"}
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body

    user = await db_session.scalar(select(User).where(User.email == payload["email"]))
    assert user is not None
    assert user.password_hash is None
    assert user.is_verified is True

    oauth_account = await db_session.scalar(
        select(OAuthAccount).where(OAuthAccount.provider_user_id == payload["sub"])
    )
    assert oauth_account is not None
    assert oauth_account.user_id == user.id
    assert oauth_account.email == payload["email"]

    role = await db_session.get(Role, user.role_id)
    assert role.name == DEFAULT_ROLE


@pytest.mark.anyio
async def test_google_sign_in_links_existing_verified_local_user(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    existing = await registered_user_with_role(RoleEnum.USER)
    payload = make_payload(email=existing["email"], email_verified=True)

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        response = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "fake-token"}
        )

    assert response.status_code == status.HTTP_200_OK

    # still exactly one user with that email
    users = (
        await db_session.scalars(select(User).where(User.email == existing["email"]))
    ).all()
    assert len(users) == 1

    oauth_account = await db_session.scalar(
        select(OAuthAccount).where(OAuthAccount.provider_user_id == payload["sub"])
    )
    assert oauth_account is not None
    assert str(oauth_account.user_id) == existing["id"]


@pytest.mark.anyio
async def test_google_sign_in_returning_user_reuses_account(
    client: AsyncClient, db_session: AsyncSession
):
    payload = make_payload()

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        first = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "fake-token"}
        )
    assert first.status_code == status.HTTP_200_OK

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        second = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "fake-token"}
        )
    assert second.status_code == status.HTTP_200_OK

    users = (
        await db_session.scalars(select(User).where(User.email == payload["email"]))
    ).all()
    assert len(users) == 1

    oauth_accounts = (
        await db_session.scalars(
            select(OAuthAccount).where(OAuthAccount.provider_user_id == payload["sub"])
        )
    ).all()
    assert len(oauth_accounts) == 1


@pytest.mark.anyio
async def test_google_sign_in_updates_email_snapshot_on_provider_email_change(
    client: AsyncClient, db_session: AsyncSession
):
    payload = make_payload()

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        await client.post(f"{API_VERSION}/auth/google", json={"id_token": "fake-token"})

    new_payload = {**payload, "email": "changed_" + payload["email"]}
    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token",
        return_value=new_payload,
    ):
        response = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "fake-token"}
        )

    assert response.status_code == status.HTTP_200_OK

    oauth_account = await db_session.scalar(
        select(OAuthAccount).where(OAuthAccount.provider_user_id == payload["sub"])
    )
    assert oauth_account.email == new_payload["email"]

    # the underlying User row's email should NOT have changed (per our design decision)
    user = await db_session.get(User, oauth_account.user_id)
    assert user.email == payload["email"]


@pytest.mark.anyio
async def test_google_sign_in_invalid_token_returns_401(client: AsyncClient):
    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token",
        side_effect=ValueError("Token expired"),
    ):
        response = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "garbage"}
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_google_sign_in_email_case_insensitive_matches_existing_user(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    existing = await registered_user_with_role(RoleEnum.USER)

    # Google reports the email with different casing than what's stored
    payload = make_payload(
        email=existing["email"].upper(),
        email_verified=True,
    )

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        response = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "fake-token"}
        )

    assert response.status_code == status.HTTP_200_OK

    # should link to the SAME existing user, not create a new one
    users = (
        await db_session.scalars(
            select(User).where(User.email == existing["email"].lower())
        )
    ).all()
    assert len(users) == 1

    oauth_account = await db_session.scalar(
        select(OAuthAccount).where(OAuthAccount.provider_user_id == payload["sub"])
    )
    assert str(oauth_account.user_id) == existing["id"]


@pytest.mark.anyio
async def test_google_sign_in_stores_email_lowercase_on_new_user(
    client: AsyncClient, db_session: AsyncSession
):
    mixed_case_email = f"Test_{uuid.uuid4().hex[:8]}@Gmail.com"
    payload = make_payload(email=mixed_case_email, email_verified=True)

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        response = await client.post(
            f"{API_VERSION}/auth/google", json={"id_token": "fake-token"}
        )

    assert response.status_code == status.HTTP_200_OK

    user = await db_session.scalar(
        select(User).where(User.email == mixed_case_email.lower())
    )
    assert user is not None

    # confirm the mixed-case version does NOT exist as a separate row
    mismatched = await db_session.scalar(
        select(User).where(User.email == mixed_case_email)
    )
    assert mismatched is None


@pytest.mark.anyio
async def test_forgot_password_existing_user_creates_token_and_returns_generic_message(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user_with_role,
):
    user = await registered_user_with_role(DEFAULT_ROLE)

    with patch(
        "app.core.email.FastApiMailSender.send_password_reset_mail",
    ):
        response = await client.post(
            f"{API_VERSION}/auth/forgot-password", json={"email": user["email"]}
        )

    assert response.status_code == status.HTTP_200_OK  # match your actual status code
    assert "detail" in response.json()

    token_row = await db_session.scalar(
        select(ForgotPasswordToken).where(
            ForgotPasswordToken.user_id == uuid.UUID(user["id"])
        )
    )
    assert token_row is not None
    assert token_row.expires_at is not None


@pytest.mark.anyio
async def test_forgot_password_nonexistent_user_returns_same_response_no_token_created(
    client: AsyncClient, db_session: AsyncSession
):
    response = await client.post(
        f"{API_VERSION}/auth/forgot-password",
        json={"email": "doesnotexist@example.com"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert "detail" in response.json()

    tokens = (await db_session.scalars(select(ForgotPasswordToken))).all()
    assert len(tokens) == 0


@pytest.mark.anyio
async def test_forgot_password_responses_identical_for_existing_and_nonexistent_user(
    client: AsyncClient, registered_user_with_role
):
    user = await registered_user_with_role(RoleEnum.USER)

    with patch("app.core.email.FastApiMailSender.send_password_reset_mail"):
        existing_response = await client.post(
            f"{API_VERSION}/auth/forgot-password", json={"email": user["email"]}
        )

    nonexistent_response = await client.post(
        f"{API_VERSION}/auth/forgot-password", json={"email": "ghost@example.com"}
    )

    # THE core security property of this endpoint
    assert existing_response.status_code == nonexistent_response.status_code
    assert existing_response.json() == nonexistent_response.json()


@pytest.mark.anyio
async def test_forgot_password_email_case_insensitive_finds_user(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(RoleEnum.USER)

    with patch("app.core.email.FastApiMailSender.send_password_reset_mail"):
        response = await client.post(
            f"{API_VERSION}/auth/forgot-password", json={"email": user["email"].upper()}
        )

    assert response.status_code == status.HTTP_200_OK

    token_row = await db_session.scalar(
        select(ForgotPasswordToken).where(
            ForgotPasswordToken.user_id == uuid.UUID(user["id"])
        )
    )
    assert token_row is not None
