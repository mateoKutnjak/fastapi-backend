import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.auth.models import RefreshToken
from app.api.v1.auth.services import create_refresh_token
from app.core.db import AsyncSession
from app.core.exceptions.error_codes import ErrorDetail
from app.core.security import hash_string
from tests.conftest import API_VERSION


@pytest.mark.asyncio
async def test_logout_revokes_only_the_given_refresh_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    other_refresh_token = await create_refresh_token(db_session, user["id"], 60)

    response = await client.post(
        f"{API_VERSION}/auth/logout",
        json={"refresh_token": user["refresh_token"]},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    revoked = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_string(user["refresh_token"])
        )
    )
    assert revoked is None

    # the other device's session must remain untouched
    still_active = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_string(other_refresh_token)
        )
    )
    assert still_active is not None


@pytest.mark.asyncio
async def test_logout_makes_refresh_token_unusable(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    logout_response = await client.post(
        f"{API_VERSION}/auth/logout",
        json={"refresh_token": user["refresh_token"]},
    )
    assert logout_response.status_code == status.HTTP_204_NO_CONTENT

    refresh_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
    )
    data = refresh_response.json()

    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == ErrorDetail.UNAUTHORIZED.value


@pytest.mark.asyncio
async def test_logout_nonexistent_token_is_idempotent(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/logout",
        json={"refresh_token": "not-a-real-token"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_logout_missing_field_returns_422(client: AsyncClient):
    response = await client.post(f"{API_VERSION}/auth/logout", json={})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_logout_all_requires_authentication(client: AsyncClient):
    response = await client.post(f"{API_VERSION}/auth/logout-all")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    second_refresh_token = await create_refresh_token(db_session, user["id"], 60)

    response = await client.post(
        f"{API_VERSION}/auth/logout-all",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    remaining = (
        await db_session.scalars(
            select(RefreshToken).where(RefreshToken.user_id == uuid.UUID(user["id"]))
        )
    ).all()
    assert remaining == []

    # both sessions must now be rejected by /refresh
    for token in (user["refresh_token"], second_refresh_token):
        refresh_response = await client.post(
            f"{API_VERSION}/auth/refresh",
            json={"refresh_token": token},
        )
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_logout_all_does_not_affect_other_users_sessions(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role: dict
):
    user_a = await registered_user_with_role("user")
    user_b = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/logout-all",
        headers={"Authorization": f"Bearer {user_a['access_token']}"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    user_b_token = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_string(user_b["refresh_token"])
        )
    )
    assert user_b_token is not None
