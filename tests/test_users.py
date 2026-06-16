import pytest
from httpx import AsyncClient

from tests.conftest import API_VERSION


@pytest.mark.asyncio
async def test_get_me_returns_current_user(
    client: AsyncClient, registered_user_with_role
):
    user = await registered_user_with_role("user")

    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user["id"]
    assert data["username"] == user["username"]
    assert data["email"] == user["email"]


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get(f"{API_VERSION}/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        f"{API_VERSION}/users/me",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name, expected_status",
    [
        ("user", 403),
        ("admin", 200),
        ("superadmin", 200),
    ],
)
async def test_get_user_by_id(
    client: AsyncClient,
    registered_user_with_role,
    role_name,
    expected_status,
):
    user = await registered_user_with_role(role_name)

    response = await client.get(
        f"{API_VERSION}/users/{user['id']}",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    assert response.status_code == expected_status

    if expected_status == 200:
        data = response.json()
        assert data["id"] == user["id"]
        assert data["username"] == user["username"]
        assert data["email"] == user["email"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name, expected_status",
    [
        ("user", 403),
        ("admin", 403),
        ("superadmin", 200),
    ],
)
async def test_get_all_users_for_roles(
    client: AsyncClient, registered_user_with_role, role_name, expected_status
):
    user = await registered_user_with_role(role_name)

    response = await client.get(
        f"{API_VERSION}/users/",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )
    assert response.status_code == expected_status
