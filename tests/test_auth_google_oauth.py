import uuid
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.auth.models import OAuthAccount
from app.api.v1.users.constants import DEFAULT_ROLE, RoleEnum
from app.api.v1.users.models import Role, User
from app.core.db import AsyncSession
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
