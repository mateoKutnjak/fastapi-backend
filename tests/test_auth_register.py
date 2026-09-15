import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import API_VERSION


@pytest.mark.asyncio
async def test_register_user_validation_error(client: AsyncClient):
    response = await client.post(
        f"{API_VERSION}/auth/register",
        json={
            "username": "testuser",
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
