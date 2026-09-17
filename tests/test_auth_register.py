import pytest
from fastapi import status
from httpx import AsyncClient

from app.config import settings
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from tests.conftest import API_VERSION


@pytest.mark.asyncio
async def test_register_user_validation_error(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
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
    assert data["error"]["detail"] == ErrorDetail.CONFLICT.value
    assert data["error"]["fields"]["email"] == ErrorCode.EMAIL_ALREADY_EXISTS.value


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
    assert data["error"]["detail"] == ErrorDetail.CONFLICT.value
    assert len(data["error"]["fields"]) == 1
    assert (
        data["error"]["fields"]["username"] == ErrorCode.USERNAME_ALREADY_EXISTS.value
    )


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
@pytest.mark.parametrize(
    "password",
    [
        "x" * (settings.password_min_length - 1),
        "x" * (settings.password_max_length + 1),
    ],
)
async def test_register_user_rejects_password_outside_policy(
    client: AsyncClient, password: str
):
    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": "password_policy_user",
            "email": f"{password[:8]}@example.com",
            "password": password,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "password" in response.text
