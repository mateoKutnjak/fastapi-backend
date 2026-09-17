import datetime

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.auth.models import ForgotPasswordToken
from app.api.v1.auth.services import forgot_password
from app.config import settings
from app.core.db import AsyncSession
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.security import hash_string
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response, assert_validation_response


@pytest.mark.asyncio
async def test_reset_password_success_changes_password_and_consumes_token(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user_with_role: dict,
):
    user = await registered_user_with_role("user")
    raw_token = await forgot_password(db_session, user["email"])

    response = await client.post(
        f"{API_VERSION}/auth/reset-password",
        json={"token": raw_token, "new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["detail"] == "Password has been reset successfully"

    old_password_response = await client.post(
        f"{API_VERSION}/auth/login",
        json={"identifier": user["email"], "password": user["password"]},
    )
    assert old_password_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        old_password_response, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )

    new_password_response = await client.post(
        f"{API_VERSION}/auth/login",
        json={"identifier": user["email"], "password": "newpassword123"},
    )
    assert new_password_response.status_code == status.HTTP_200_OK

    refresh_response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
    )
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        refresh_response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )

    token_row = await db_session.scalar(
        select(ForgotPasswordToken).where(
            ForgotPasswordToken.token_hash == hash_string(raw_token)
        )
    )
    assert token_row is None


@pytest.mark.asyncio
async def test_reset_password_invalid_token_returns_401(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_PASSWORD_RESET_TOKEN, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_reset_password_expired_token_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user_with_role: dict,
):
    user = await registered_user_with_role("user")
    raw_token = await forgot_password(db_session, user["email"])

    token_row = await db_session.scalar(
        select(ForgotPasswordToken).where(
            ForgotPasswordToken.token_hash == hash_string(raw_token)
        )
    )
    token_row.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        seconds=1
    )
    await db_session.flush()

    response = await client.post(
        f"{API_VERSION}/auth/reset-password",
        json={"token": raw_token, "new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.EXPIRED_PASSWORD_RESET_TOKEN, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_reset_password_token_can_only_be_used_once(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user_with_role: dict,
):
    user = await registered_user_with_role("user")
    raw_token = await forgot_password(db_session, user["email"])

    first_response = await client.post(
        f"{API_VERSION}/auth/reset-password",
        json={"token": raw_token, "new_password": "newpassword123"},
    )
    assert first_response.status_code == status.HTTP_200_OK

    second_response = await client.post(
        f"{API_VERSION}/auth/reset-password",
        json={"token": raw_token, "new_password": "anotherpassword123"},
    )

    assert second_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        second_response,
        ErrorCode.INVALID_PASSWORD_RESET_TOKEN,
        ErrorDetail.UNAUTHORIZED,
    )


@pytest.mark.asyncio
async def test_reset_password_missing_field_returns_422(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/reset-password",
        json={"new_password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_validation_response(response)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new_password",
    [
        "x" * (settings.password_min_length - 1),
        "x" * (settings.password_max_length + 1),
    ],
)
async def test_reset_password_rejects_password_outside_policy(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user_with_role: dict,
    new_password: str,
):
    user = await registered_user_with_role("user")
    raw_token = await forgot_password(db_session, user["email"])

    response = await client.post(
        f"{API_VERSION}/auth/reset-password",
        json={"token": raw_token, "new_password": new_password},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_validation_response(response)
    assert "new_password" in response.text
