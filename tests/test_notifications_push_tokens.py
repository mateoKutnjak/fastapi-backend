import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.notifications.models import PushNotificationToken
from app.api.v1.users.constants import DEFAULT_ROLE
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response, assert_validation_response

PUSH_TOKENS_URL = f"{API_VERSION}/notifications/push-tokens"
UNLINK_URL = f"{PUSH_TOKENS_URL}/unlink"


def new_device() -> tuple[str, str]:
    return f"fid-{uuid.uuid4().hex}", f"token-{uuid.uuid4().hex}"


def auth(user: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['access_token']}"}


async def get_push_token(
    db_session: AsyncSession, fid: str
) -> PushNotificationToken | None:
    return await db_session.scalar(
        select(PushNotificationToken).where(PushNotificationToken.fid == fid)
    )


async def register(client: AsyncClient, fid: str, token: str, headers=None):
    return await client.post(
        PUSH_TOKENS_URL, json={"fid": fid, "token": token}, headers=headers
    )


async def unlink(client: AsyncClient, fid: str, headers=None):
    return await client.put(UNLINK_URL, json={"fid": fid}, headers=headers)


async def delete(client: AsyncClient, fid: str, headers=None):
    # httpx's delete() has no body support, so use request() directly.
    return await client.request(
        "DELETE", PUSH_TOKENS_URL, json={"fid": fid}, headers=headers
    )


# --- register ---


@pytest.mark.anyio
async def test_register_anonymous_creates_token_without_owner(
    client: AsyncClient, db_session: AsyncSession
):
    fid, token = new_device()

    response = await register(client, fid, token)

    assert response.status_code == status.HTTP_201_CREATED
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.token == token
    assert stored.user_id is None


@pytest.mark.anyio
async def test_register_authenticated_links_token_to_user(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()

    response = await register(client, fid, token, headers=auth(user))

    assert response.status_code == status.HTTP_201_CREATED
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.user_id == uuid.UUID(user["id"])


@pytest.mark.anyio
async def test_register_same_fid_updates_token_without_duplicating(
    client: AsyncClient, db_session: AsyncSession
):
    fid, token = new_device()
    _, rotated_token = new_device()

    await register(client, fid, token)
    response = await register(client, fid, rotated_token)

    assert response.status_code == status.HTTP_201_CREATED
    count = await db_session.scalar(
        select(func.count())
        .select_from(PushNotificationToken)
        .where(PushNotificationToken.fid == fid)
    )
    assert count == 1
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.token == rotated_token


@pytest.mark.anyio
async def test_register_owner_can_rotate_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    _, rotated_token = new_device()

    await register(client, fid, token, headers=auth(user))
    response = await register(client, fid, rotated_token, headers=auth(user))

    assert response.status_code == status.HTTP_201_CREATED
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.token == rotated_token
    assert stored.user_id == uuid.UUID(user["id"])


@pytest.mark.anyio
async def test_register_login_after_anonymous_registration_links_user(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()

    await register(client, fid, token)
    await register(client, fid, token, headers=auth(user))

    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.user_id == uuid.UUID(user["id"])


@pytest.mark.anyio
async def test_register_anonymous_cannot_update_existing_owner(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    _, attempted_token = new_device()
    await register(client, fid, token, headers=auth(user))

    response = await register(client, fid, attempted_token)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert_error_response(
        response,
        ErrorCode.FCM_TOKEN_UPDATE_FORBIDDEN,
        ErrorDetail.FORBIDDEN,
    )
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.token == token
    assert stored.user_id == uuid.UUID(user["id"])


@pytest.mark.anyio
async def test_register_by_another_user_cannot_update_existing_owner(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    owner = await registered_user_with_role(DEFAULT_ROLE)
    other_user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    _, attempted_token = new_device()

    await register(client, fid, token, headers=auth(owner))
    response = await register(client, fid, attempted_token, headers=auth(other_user))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert_error_response(
        response,
        ErrorCode.FCM_TOKEN_UPDATE_FORBIDDEN,
        ErrorDetail.FORBIDDEN,
    )
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.token == token
    assert stored.user_id == uuid.UUID(owner["id"])


@pytest.mark.anyio
async def test_register_with_invalid_access_token_is_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    fid, token = new_device()

    response = await register(
        client, fid, token, headers={"Authorization": "Bearer invalid-token"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )
    assert await get_push_token(db_session, fid) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body,fields",
    [
        ({"token": "t"}, {"fid": "missing"}),
        ({"fid": "f"}, {"token": "missing"}),
        ({}, {"fid": "missing", "token": "missing"}),
    ],
)
async def test_register_requires_fid_and_token(
    client: AsyncClient, body: dict, fields: dict[str, str]
):
    response = await client.post(PUSH_TOKENS_URL, json=body)

    assert_validation_response(response, fields)


# --- unlink ---


@pytest.mark.anyio
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
async def test_unlink_requires_authentication(client: AsyncClient, headers):
    response = await unlink(client, "any-fid", headers=headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.anyio
async def test_unlink_removes_owner_but_keeps_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    await register(client, fid, token, headers=auth(user))

    response = await unlink(client, fid, headers=auth(user))

    assert response.status_code == status.HTTP_200_OK
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.user_id is None
    assert stored.token == token


@pytest.mark.anyio
async def test_unlink_by_another_user_changes_nothing(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    owner = await registered_user_with_role(DEFAULT_ROLE)
    other = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    await register(client, fid, token, headers=auth(owner))

    response = await unlink(client, fid, headers=auth(other))

    assert response.status_code == status.HTTP_200_OK
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.user_id == uuid.UUID(owner["id"])


@pytest.mark.anyio
async def test_unlink_unknown_fid_is_a_no_op(
    client: AsyncClient, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)

    response = await unlink(client, "unknown-fid", headers=auth(user))

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.anyio
async def test_unlink_requires_fid(client: AsyncClient, registered_user_with_role):
    user = await registered_user_with_role(DEFAULT_ROLE)

    response = await client.put(UNLINK_URL, json={}, headers=auth(user))

    assert_validation_response(response, {"fid": "missing"})


# --- delete ---


@pytest.mark.anyio
async def test_delete_anonymous_removes_token_without_owner(
    client: AsyncClient, db_session: AsyncSession
):
    fid, token = new_device()
    await register(client, fid, token)

    response = await delete(client, fid)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""
    assert await get_push_token(db_session, fid) is None


@pytest.mark.anyio
async def test_delete_anonymous_cannot_remove_owned_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    await register(client, fid, token, headers=auth(user))

    response = await delete(client, fid)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.user_id == uuid.UUID(user["id"])


@pytest.mark.anyio
async def test_delete_by_owner_removes_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    await register(client, fid, token, headers=auth(user))

    response = await delete(client, fid, headers=auth(user))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert await get_push_token(db_session, fid) is None


@pytest.mark.anyio
async def test_delete_by_another_user_cannot_remove_owned_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    owner = await registered_user_with_role(DEFAULT_ROLE)
    other = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    await register(client, fid, token, headers=auth(owner))

    response = await delete(client, fid, headers=auth(other))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    stored = await get_push_token(db_session, fid)
    assert stored is not None
    assert stored.user_id == uuid.UUID(owner["id"])


@pytest.mark.anyio
async def test_delete_by_authenticated_user_removes_ownerless_token(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(DEFAULT_ROLE)
    fid, token = new_device()
    await register(client, fid, token)

    response = await delete(client, fid, headers=auth(user))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert await get_push_token(db_session, fid) is None


@pytest.mark.anyio
async def test_delete_unknown_fid_is_a_no_op(client: AsyncClient):
    response = await delete(client, "unknown-fid")

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.anyio
async def test_delete_with_invalid_access_token_is_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    fid, token = new_device()
    await register(client, fid, token)

    response = await delete(
        client, fid, headers={"Authorization": "Bearer invalid-token"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert await get_push_token(db_session, fid) is not None


@pytest.mark.anyio
async def test_delete_requires_fid(client: AsyncClient):
    response = await client.request("DELETE", PUSH_TOKENS_URL, json={})

    assert_validation_response(response, {"fid": "missing"})
