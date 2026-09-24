import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.auth.models import Session
from app.api.v1.auth.schemas import SessionMetadata
from app.api.v1.auth.services import create_refresh_token
from app.core.db import AsyncSession
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.security import create_access_token, hash_string
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response


@pytest.mark.asyncio
async def test_logout_revokes_only_current_session(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    other_refresh_token, _ = await create_refresh_token(
        db_session, uuid.UUID(user["id"]), SessionMetadata(), 60, 120
    )

    response = await client.post(
        f"{API_VERSION}/auth/logout",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    revoked = await db_session.scalar(
        select(Session).where(
            Session.refresh_token_hash == hash_string(user["refresh_token"])
        )
    )
    assert revoked is not None
    assert revoked.revoked_at is not None

    # the other device's session must remain untouched
    still_active = await db_session.scalar(
        select(Session).where(
            Session.refresh_token_hash == hash_string(other_refresh_token)
        )
    )
    assert still_active is not None
    assert still_active.revoked_at is None
    other_refresh = await client.post(
        f"{API_VERSION}/auth/refresh", json={"refresh_token": other_refresh_token}
    )
    assert other_refresh.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_logout_makes_refresh_token_unusable(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    logout_response = await client.post(
        f"{API_VERSION}/auth/logout",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    assert logout_response.status_code == status.HTTP_204_NO_CONTENT

    me = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    assert me.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(me, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED)
    repeated = await client.post(
        f"{API_VERSION}/auth/logout",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    assert repeated.status_code == status.HTTP_401_UNAUTHORIZED

    refresh_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
    )

    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        refresh_response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
async def test_logout_requires_valid_authentication(client: AsyncClient, headers):
    response = await client.post(f"{API_VERSION}/auth/logout", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_logout_all_requires_authentication(client: AsyncClient):
    response = await client.post(f"{API_VERSION}/auth/logout-all")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    second_refresh_token, _ = await create_refresh_token(
        db_session, uuid.UUID(user["id"]), SessionMetadata(), 60, 120
    )

    response = await client.post(
        f"{API_VERSION}/auth/logout-all",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    remaining = (
        await db_session.scalars(
            select(Session).where(Session.user_id == uuid.UUID(user["id"]))
        )
    ).all()
    assert {row.refresh_token_hash for row in remaining} == {
        hash_string(user["refresh_token"]),
        hash_string(second_refresh_token),
    }
    assert all(session.revoked_at is not None for session in remaining)

    for row in remaining:
        me = await client.get(
            f"{API_VERSION}/users/me",
            headers={
                "Authorization": f"Bearer {create_access_token(row.user_id, row.id)}"
            },
        )
        assert me.status_code == status.HTTP_401_UNAUTHORIZED
        assert_error_response(
            me, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
        )

    # both sessions must now be rejected by /refresh
    for token in (user["refresh_token"], second_refresh_token):
        refresh_response = await client.post(
            f"{API_VERSION}/auth/refresh",
            json={"refresh_token": token},
        )
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert_error_response(
            refresh_response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
        )


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
        select(Session).where(
            Session.refresh_token_hash == hash_string(user_b["refresh_token"])
        )
    )
    assert user_b_token is not None
    assert user_b_token.revoked_at is None
    me = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user_b['access_token']}"},
    )
    assert me.status_code == status.HTTP_200_OK
