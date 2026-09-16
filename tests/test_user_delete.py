import uuid
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.models import (
    EmailVerificationToken,
    ForgotPasswordToken,
    OAuthAccount,
)
from app.api.v1.users.constants import DEFAULT_ROLE, RoleEnum
from app.api.v1.users.models import User
from tests.conftest import API_VERSION


@pytest.mark.anyio
async def test_delete_me_removes_own_account(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)

    response = await client.delete(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""

    deleted = await db_session.get(User, uuid.UUID(user["id"]))
    assert deleted is None


@pytest.mark.anyio
async def test_delete_me_requires_authentication(client: AsyncClient):
    response = await client.delete(f"{API_VERSION}/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_delete_user_requires_authentication(client: AsyncClient):
    response = await client.delete(f"{API_VERSION}/users/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_delete_me_cascades_related_records(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    user_id = uuid.UUID(user["id"])

    # sanity check: EmailVerificationToken row should exist from registration
    token_before = await db_session.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
    )
    assert token_before is not None

    response = await client.delete(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    token_after = await db_session.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
    )
    assert token_after is None


@pytest.mark.anyio
async def test_delete_me_cascades_forgot_password_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(RoleEnum.USER)
    user_id = uuid.UUID(user["id"])

    # create a ForgotPasswordToken row via the real flow
    with patch("app.core.email.FastApiMailSender.send_password_reset_mail"):
        forgot_response = await client.post(
            f"{API_VERSION}/auth/forgot-password", json={"email": user["email"]}
        )
    assert forgot_response.status_code == status.HTTP_200_OK

    token_before = await db_session.scalar(
        select(ForgotPasswordToken).where(ForgotPasswordToken.user_id == user_id)
    )
    assert token_before is not None

    response = await client.delete(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    token_after = await db_session.scalar(
        select(ForgotPasswordToken).where(ForgotPasswordToken.user_id == user_id)
    )
    assert token_after is None


@pytest.mark.anyio
async def test_delete_me_cascades_oauth_account(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(RoleEnum.USER)
    user_id = uuid.UUID(user["id"])

    oauth_account = OAuthAccount(
        user_id=user_id,
        provider="google",
        provider_user_id=f"google-{uuid.uuid4().hex}",
        email=user["email"],
    )
    db_session.add(oauth_account)
    await db_session.flush()

    response = await client.delete(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    oauth_account_after = await db_session.scalar(
        select(OAuthAccount).where(OAuthAccount.user_id == user_id)
    )
    assert oauth_account_after is None


@pytest.mark.anyio
async def test_delete_me_only_deletes_own_account_not_others(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user_a = await registered_user_with_role(DEFAULT_ROLE)
    user_b = await registered_user_with_role(DEFAULT_ROLE)

    response = await client.delete(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user_a['access_token']}"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # user_a gone, user_b untouched
    assert await db_session.get(User, uuid.UUID(user_a["id"])) is None
    assert await db_session.get(User, uuid.UUID(user_b["id"])) is not None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "role,expected_status",
    [
        (RoleEnum.USER, status.HTTP_403_FORBIDDEN),
        (RoleEnum.ADMIN, status.HTTP_403_FORBIDDEN),
        (RoleEnum.SUPERADMIN, status.HTTP_404_NOT_FOUND),
    ],
)
async def test_delete_nonexistent_user_returns_404(
    client: AsyncClient, registered_user_with_role, role, expected_status
):
    superadmin = await registered_user_with_role(role)
    fake_id = uuid.uuid4()

    response = await client.delete(
        f"{API_VERSION}/users/{fake_id}",
        headers={"Authorization": f"Bearer {superadmin['access_token']}"},
    )

    assert response.status_code == expected_status


@pytest.mark.anyio
@pytest.mark.parametrize(
    "role,expected_status",
    [
        (RoleEnum.USER, status.HTTP_403_FORBIDDEN),
        (RoleEnum.ADMIN, status.HTTP_403_FORBIDDEN),
        (RoleEnum.SUPERADMIN, status.HTTP_422_UNPROCESSABLE_CONTENT),
    ],
)
async def test_delete_user_invalid_uuid_returns_422(
    client: AsyncClient, registered_user_with_role, role, expected_status
):
    superadmin = await registered_user_with_role(role)

    response = await client.delete(
        f"{API_VERSION}/users/not-a-uuid",
        headers={"Authorization": f"Bearer {superadmin['access_token']}"},
    )

    assert response.status_code == expected_status
