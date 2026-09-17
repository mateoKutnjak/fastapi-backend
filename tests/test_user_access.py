import uuid

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.security import create_access_token
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response


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

    assert response.status_code == expected_status
    if expected_status == status.HTTP_403_FORBIDDEN:
        assert_error_response(
            response, ErrorCode.PERMISSION_DENIED, ErrorDetail.FORBIDDEN
        )
    elif expected_status == status.HTTP_404_NOT_FOUND:
        assert_error_response(response, ErrorCode.USER_NOT_FOUND, ErrorDetail.NOT_FOUND)


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

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


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
    if expected_status == status.HTTP_403_FORBIDDEN:
        assert_error_response(
            response, ErrorCode.PERMISSION_DENIED, ErrorDetail.FORBIDDEN
        )

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
    if expected_status == status.HTTP_403_FORBIDDEN:
        assert_error_response(
            response, ErrorCode.PERMISSION_DENIED, ErrorDetail.FORBIDDEN
        )


@pytest.mark.asyncio
async def test_access_token_for_missing_user_hides_user_not_found(client: AsyncClient):
    response = await client.get(
        f"{API_VERSION}/users/me",
        headers={"Authorization": f"Bearer {create_access_token(uuid.uuid4())}"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )
