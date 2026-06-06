import pytest
from httpx import AsyncClient

from app.core.security import TokenType, create_token


@pytest.mark.asyncio
async def test_register_user_validation_error(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
        },
    )
    assert response.status_code == 422
    assert "email" in response.text
    assert "password" in response.text


@pytest.mark.asyncio
async def test_register_user_duplicate_email(
    client: AsyncClient, registered_user: dict
):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": registered_user["email"],
            "password": "newpassword123",
        },
    )

    assert response.status_code == 409
    assert "Email already exists" in response.text


@pytest.mark.asyncio
async def test_register_user_duplicate_username(
    client: AsyncClient, registered_user: dict
):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": registered_user["username"],
            "email": "newemail@example.com",
            "password": "newpassword123",
        },
    )

    assert response.status_code == 409
    assert "Username already exists" in response.text


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_login_user_invalid_credentials(
    client: AsyncClient, registered_user: dict
):
    response = await client.post(
        "/api/auth/token",
        data={
            "username": registered_user["email"],
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 409
    assert "Invalid email or password" in response.text


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient, registered_user: dict):
    response = await client.post(
        "/api/auth/token",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_expired_access_token(client: AsyncClient, registered_user: dict):
    expired_access_token = create_token(
        registered_user["id"], TokenType.ACCESS, expires_delta=-5
    )

    response = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {expired_access_token}"},
    )

    assert response.status_code == 401
    assert "Token has expired" in response.text


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, registered_user: dict):
    response = await client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": registered_user["refresh_token"],
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio
async def test_refresh_token_invalid_token(client: AsyncClient):
    response = await client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": "invalidtoken",
        },
    )

    assert response.status_code == 401
    assert "Token is malformed" in response.text


@pytest.mark.asyncio
async def test_refresh_token_expired_token(client: AsyncClient, registered_user: dict):
    expired_refresh_token = create_token(
        registered_user["id"], TokenType.REFRESH, expires_delta=-5
    )

    response = await client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": expired_refresh_token,
        },
    )

    assert response.status_code == 401
    assert "Token has expired" in response.text
