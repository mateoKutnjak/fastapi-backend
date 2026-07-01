import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.security import TokenType, create_token
from tests.conftest import API_VERSION


@pytest.mark.asyncio
async def test_register_user_validation_error(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": "testuser",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
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
    assert data["error"]["detail"] == "Conflict"
    assert data["error"]["fields"]["email"] == "Email already exists"


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
    assert data["error"]["detail"] == "Conflict"
    assert len(data["error"]["fields"]) == 1
    assert data["error"]["fields"]["username"] == "Username already exists"


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
async def test_login_user_invalid_credentials(
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

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient, registered_user_with_role: dict):
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
async def test_expired_access_token(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    expired_access_token = create_token(user["id"], TokenType.ACCESS, expires_delta=-5)

    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {expired_access_token}"},
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["status_code"] == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


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
    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["status_code"] == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_expired_token(
    client: AsyncClient, registered_user_with_role: dict
):
    user = await registered_user_with_role("user")

    expired_refresh_token = create_token(
        user["id"], TokenType.REFRESH, expires_delta=-5
    )

    response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={
            "refresh_token": expired_refresh_token,
        },
    )

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["status_code"] == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"
