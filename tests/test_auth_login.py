import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.security import create_access_token
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_CREDENTIALS, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_expired_access_token(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    expired_access_token = create_access_token(user["id"], expires_delta=-5)

    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {expired_access_token}"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_malformed_access_token(client: AsyncClient):
    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )
