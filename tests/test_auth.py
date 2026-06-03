import pytest
from httpx import AsyncClient


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
