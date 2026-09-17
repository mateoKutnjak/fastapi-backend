import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.auth.models import RefreshToken
from app.api.v1.auth.services import create_refresh_token
from app.core.db import AsyncSession
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.security import hash_string
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response, assert_validation_response


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_refresh_token_expired_token(
    db_session: AsyncSession, client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    expired_refresh_token = await create_refresh_token(
        db_session, user["id"], expires_delta=-5
    )

    response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={
            "refresh_token": expired_refresh_token,
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_refresh_token_missing_field(client: AsyncClient):
    response = await client.post(f"{API_VERSION}/auth/refresh", json={})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_validation_response(response)


@pytest.mark.asyncio
async def test_refresh_token_rotates_and_invalidates_old_token(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    first_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
    )
    assert first_response.status_code == status.HTTP_200_OK

    new_refresh_token = first_response.json()["refresh_token"]
    assert new_refresh_token != user["refresh_token"]

    # Reusing the old (already rotated) refresh token must now fail
    reuse_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
    )

    assert reuse_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        reuse_response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )

    # The newly issued refresh token should still work
    second_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )
    assert second_response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_refresh_token_new_access_token_grants_access(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
    )
    assert response.status_code == status.HTTP_200_OK

    new_access_token = response.json()["access_token"]

    me_response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )

    assert me_response.status_code == status.HTTP_200_OK
    assert me_response.json()["id"] == user["id"]


@pytest.mark.asyncio
async def test_refresh_token_persisted_hashed_in_db(
    db_session: AsyncSession, client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_string(user["refresh_token"])
        )
    )
    token_row = result.scalar_one_or_none()

    assert token_row is not None
    assert token_row.user_id == uuid.UUID(user["id"])
    assert token_row.expires_at is not None
