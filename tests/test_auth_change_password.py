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


@pytest.mark.anyio
async def test_change_password_success_invalidates_old_credentials_and_session(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/change-password",
        headers={"Authorization": f"Bearer {user['access_token']}"},
        json={
            "current_password": user["password"],
            "new_password": "newpassword123",
        },
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""

    old_login = await client.post(
        f"{API_VERSION}/auth/login",
        json={"identifier": user["email"], "password": user["password"]},
    )
    assert old_login.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        old_login, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )

    new_login = await client.post(
        f"{API_VERSION}/auth/login",
        json={"identifier": user["email"], "password": "newpassword123"},
    )
    assert new_login.status_code == status.HTTP_200_OK

    refresh_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
    )
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        refresh_response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.anyio
async def test_change_password_wrong_current_password_returns_401(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/change-password",
        headers={"Authorization": f"Bearer {user['access_token']}"},
        json={
            "current_password": "wrong-password",
            "new_password": "newpassword123",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_CURRENT_PASSWORD, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.anyio
async def test_change_password_requires_authentication(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/change-password",
        json={
            "current_password": "oldpassword123",
            "new_password": "newpassword123",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        {"new_password": "newpassword123"},
        {"current_password": "password123"},
        {},
    ],
)
async def test_change_password_missing_field_returns_422(
    client: AsyncClient, registered_user_with_role: dict, body: dict
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/change-password",
        headers={"Authorization": f"Bearer {user['access_token']}"},
        json=body,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_validation_response(
        response,
        {
            field: "missing"
            for field in ("current_password", "new_password")
            if field not in body
        },
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "new_password",
    [
        "x" * (settings.password_min_length - 1),
        "x" * (settings.password_max_length + 1),
    ],
)
async def test_change_password_rejects_password_outside_policy(
    client: AsyncClient,
    registered_user_with_role: dict,
    new_password: str,
):
    user = await registered_user_with_role("user")

    response = await client.post(
        f"{API_VERSION}/auth/change-password",
        headers={"Authorization": f"Bearer {user['access_token']}"},
        json={
            "current_password": user["password"],
            "new_password": new_password,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_validation_response(
        response,
        {
            "new_password": "string_too_short"
            if len(new_password) < settings.password_min_length
            else "string_too_long"
        },
    )


@pytest.mark.anyio
async def test_oauth_only_user_cannot_change_password(
    client: AsyncClient,
):
    payload = make_google_payload()

    with patch(
        "app.api.v1.auth.services.id_token.verify_oauth2_token", return_value=payload
    ):
        login_response = await client.post(
            f"{API_VERSION}/auth/oauth/google",
            json={"id_token": "fake-token"},
        )

    assert login_response.status_code == status.HTTP_200_OK

    response = await client.post(
        f"{API_VERSION}/auth/change-password",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
        json={
            "current_password": "password123",
            "new_password": "newpassword123",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.CURRENT_USER_HAS_NO_PASSWORD, ErrorDetail.UNAUTHORIZED
    )
