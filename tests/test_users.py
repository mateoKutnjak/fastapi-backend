import uuid

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import API_VERSION


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name, expected_status",
    [
        ("user", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_404_NOT_FOUND),
        ("superadmin", status.HTTP_404_NOT_FOUND),
    ],
)
async def test_get_user_by_non_existing_uuid(
    client: AsyncClient, registered_user_with_role, role_name, expected_status
):
    user = await registered_user_with_role(role_name)

    response = await client.get(
        f"{API_VERSION}/users/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    data = response.json()

    assert response.status_code == expected_status
    if expected_status == status.HTTP_404_NOT_FOUND:
        assert data["error"]["status_code"] == status.HTTP_404_NOT_FOUND
        assert data["error"]["detail"] == "Not found"
    elif expected_status == status.HTTP_403_FORBIDDEN:
        assert data["error"]["status_code"] == status.HTTP_403_FORBIDDEN
        assert data["error"]["detail"] == "Forbidden"


@pytest.mark.asyncio
async def test_get_me_returns_current_user(
    client: AsyncClient, registered_user_with_role
):
    user = await registered_user_with_role("user")

    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {user['access_token']}"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == user["id"]
    assert data["username"] == user["username"]
    assert data["email"] == user["email"]


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get(f"{API_VERSION}/users/me")

    data = response.json()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["status_code"] == status.HTTP_401_UNAUTHORIZED
    assert data["error"]["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        f"{API_VERSION}/users/me",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name, expected_status",
    [
        ("user", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_200_OK),
        ("superadmin", status.HTTP_200_OK),
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

    if expected_status == status.HTTP_200_OK:
        data = response.json()
        assert data["id"] == user["id"]
        assert data["username"] == user["username"]
        assert data["email"] == user["email"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_name, expected_status",
    [
        ("user", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        ("superadmin", status.HTTP_200_OK),
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
