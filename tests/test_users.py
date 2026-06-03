import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me_returns_current_user(
    authorized_client: AsyncClient, registered_user: dict
):
    response = await authorized_client.get(
        "/api/users/me",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == registered_user["id"]
    assert data["username"] == registered_user["username"]
    assert data["email"] == registered_user["email"]


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert response.status_code == 401


# TODO test for access token expriration


@pytest.mark.asyncio
async def test_get_user_by_id(authorized_client: AsyncClient, registered_user: dict):
    response = await authorized_client.get(
        f"/api/users/{registered_user['id']}",
        headers={"Authorization": f"Bearer {registered_user['access_token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == registered_user["id"]
    assert data["username"] == registered_user["username"]
    assert data["email"] == registered_user["email"]
