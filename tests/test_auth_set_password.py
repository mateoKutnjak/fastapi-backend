import uuid
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.config import settings
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response, assert_validation_response


def make_google_payload() -> dict:
    return {
        "sub": "google-sub-" + uuid.uuid4().hex[:12],
        "email": f"oauth_{uuid.uuid4().hex[:8]}@gmail.com",
        "email_verified": True,
        "aud": "test-client-id",
        "iss": "accounts.google.com",
    }


async def create_oauth_session(client: AsyncClient) -> tuple[dict, dict]:
    payload = make_google_payload()

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        response = await client.post(
            f"{API_VERSION}/auth/oauth/google",
            json={"id_token": "fake-token"},
        )

    assert response.status_code == status.HTTP_200_OK
    return payload, response.json()


@pytest.mark.anyio
async def test_oauth_user_can_set_password_and_login_with_email(
    client: AsyncClient,
):
    payload, oauth_tokens = await create_oauth_session(client)

    response = await client.post(
        f"{API_VERSION}/auth/set-password",
        headers={"Authorization": f"Bearer {oauth_tokens['access_token']}"},
        json={"new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""

    login_response = await client.post(
        f"{API_VERSION}/auth/login",
        json={
            "identifier": payload["email"],
            "password": "newpassword123",
        },
    )

    assert login_response.status_code == status.HTTP_200_OK
    assert "access_token" in login_response.json()
    assert "refresh_token" in login_response.json()


@pytest.mark.anyio
async def test_set_password_revokes_existing_oauth_refresh_token(
    client: AsyncClient,
):
    _, oauth_tokens = await create_oauth_session(client)

    response = await client.post(
        f"{API_VERSION}/auth/set-password",
        headers={"Authorization": f"Bearer {oauth_tokens['access_token']}"},
        json={"new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    refresh_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": oauth_tokens["refresh_token"]},
    )

    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        refresh_response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.anyio
async def test_set_password_cannot_be_used_twice(
    client: AsyncClient,
):
    payload, oauth_tokens = await create_oauth_session(client)

    first_response = await client.post(
        f"{API_VERSION}/auth/set-password",
        headers={"Authorization": f"Bearer {oauth_tokens['access_token']}"},
        json={"new_password": "newpassword123"},
    )
    assert first_response.status_code == status.HTTP_204_NO_CONTENT

    login_response = await client.post(
        f"{API_VERSION}/auth/login",
        json={"identifier": payload["email"], "password": "newpassword123"},
    )
    assert login_response.status_code == status.HTTP_200_OK

    second_response = await client.post(
        f"{API_VERSION}/auth/set-password",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
        json={"new_password": "anotherpassword123"},
    )

    assert second_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        second_response,
        ErrorCode.CURRENT_USER_ALREADY_HAS_PASSWORD,
        ErrorDetail.UNAUTHORIZED,
    )


@pytest.mark.anyio
async def test_password_user_cannot_use_set_password(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/set-password",
        headers={"Authorization": f"Bearer {user['access_token']}"},
        json={"new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.CURRENT_USER_ALREADY_HAS_PASSWORD, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.anyio
async def test_set_password_requires_authentication(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/set-password",
        json={"new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.anyio
async def test_set_password_missing_field_returns_422(client: AsyncClient):
    _, oauth_tokens = await create_oauth_session(client)

    response = await client.post(
        f"{API_VERSION}/auth/set-password",
        headers={"Authorization": f"Bearer {oauth_tokens['access_token']}"},
        json={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_validation_response(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "new_password",
    [
        "x" * (settings.password_min_length - 1),
        "x" * (settings.password_max_length + 1),
    ],
)
async def test_set_password_rejects_password_outside_policy(
    client: AsyncClient,
    new_password: str,
):
    _, oauth_tokens = await create_oauth_session(client)

    response = await client.post(
        f"{API_VERSION}/auth/set-password",
        headers={"Authorization": f"Bearer {oauth_tokens['access_token']}"},
        json={"new_password": new_password},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_validation_response(response)
