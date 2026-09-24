import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import status
from sqlalchemy import select

from app.api.v1.auth.models import Session
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.security import create_access_token, hash_string, verify_access_token
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalidity", ["revoked", "expired", "absolute_expired", "missing", "wrong_owner"]
)
async def test_access_rejects_invalid_session(
    client, db_session, registered_user_with_role, invalidity
):
    user = await registered_user_with_role("user")
    user_id, session_id = verify_access_token(user["access_token"])
    session = await db_session.get(Session, session_id)
    now = datetime.now(UTC)
    token = user["access_token"]
    if invalidity == "revoked":
        session.revoked_at = now
    elif invalidity == "expired":
        session.expires_at = now - timedelta(seconds=1)
    elif invalidity == "absolute_expired":
        session.absolute_expires_at = now - timedelta(seconds=1)
    elif invalidity == "missing":
        token = create_access_token(user_id, uuid.uuid4())
    else:
        other = await registered_user_with_role("user")
        token = create_access_token(other["id"], session_id)
    await db_session.flush()
    response = await client.get(
        f"{API_VERSION}/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.AUTHENTICATION_FAILED, ErrorDetail.UNAUTHORIZED
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("invalidity", ["revoked", "absolute_expired"])
async def test_refresh_rejects_invalid_session(
    client, db_session, registered_user_with_role, invalidity
):
    user = await registered_user_with_role("user")
    _, session_id = verify_access_token(user["access_token"])
    session = await db_session.get(Session, session_id)
    if invalidity == "revoked":
        session.revoked_at = datetime.now(UTC)
    else:
        session.absolute_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    old_hash = session.refresh_token_hash
    await db_session.flush()
    response = await client.post(
        f"{API_VERSION}/auth/refresh", json={"refresh_token": user["refresh_token"]}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_error_response(
        response, ErrorCode.INVALID_REFRESH_TOKEN, ErrorDetail.UNAUTHORIZED
    )
    await db_session.refresh(session)
    assert session.refresh_token_hash == old_hash


@pytest.mark.asyncio
async def test_refresh_preserves_session_metadata_and_absolute_deadline(
    client, db_session, registered_user_with_role
):
    user = await registered_user_with_role("user")
    _, session_id = verify_access_token(user["access_token"])
    session = await db_session.get(Session, session_id)
    deadline = datetime.now(UTC) + timedelta(minutes=30)
    session.absolute_expires_at = deadline
    session.expires_at = datetime.now(UTC) + timedelta(minutes=5)
    session.device_name = "My phone"
    session.device_id = "device-123"
    session.user_agent = "Original agent"
    session.ip_address = "192.0.2.1"
    await db_session.flush()
    response = await client.post(
        f"{API_VERSION}/auth/refresh",
        json={"refresh_token": user["refresh_token"]},
        headers={"User-Agent": "Different agent"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert verify_access_token(response.json()["access_token"])[1] == session_id
    await db_session.refresh(session)
    assert session.absolute_expires_at == deadline
    assert session.expires_at == deadline
    assert session.refresh_token_hash == hash_string(response.json()["refresh_token"])
    assert (
        session.device_name,
        session.device_id,
        session.user_agent,
        session.ip_address,
    ) == ("My phone", "device-123", "Original agent", "192.0.2.1")


@pytest.mark.asyncio
@pytest.mark.parametrize("flow", ["register", "login", "token", "google"])
async def test_session_creation_stores_request_metadata(
    client, db_session, registered_user_with_role, flow
):
    headers = {
        "X-Device-Name": "Test phone",
        "X-Device-ID": "device-abc",
        "User-Agent": "Test agent",
    }
    if flow == "register":
        response = await client.post(
            f"{API_VERSION}/auth/register",
            headers=headers,
            json={
                "username": "metadatauser",
                "email": "metadata@example.com",
                "password": "testpassword123",
            },
        )
    elif flow == "google":
        payload = {
            "sub": "metadata-google",
            "email": "metadata@gmail.com",
            "email_verified": True,
        }
        with patch(
            "app.api.v1.auth.services.id_token.verify_oauth2_token",
            return_value=payload,
        ):
            response = await client.post(
                f"{API_VERSION}/auth/oauth/google",
                headers=headers,
                json={"id_token": "fake-token"},
            )
    else:
        user = await registered_user_with_role("user")
        if flow == "login":
            response = await client.post(
                f"{API_VERSION}/auth/login",
                headers=headers,
                json={"identifier": user["email"], "password": user["password"]},
            )
        else:
            response = await client.post(
                f"{API_VERSION}/auth/token",
                headers=headers,
                data={"username": user["email"], "password": user["password"]},
            )
    assert response.status_code == (201 if flow == "register" else 200)
    row = await db_session.scalar(
        select(Session).where(
            Session.refresh_token_hash == hash_string(response.json()["refresh_token"])
        )
    )
    assert row is not None
    assert row.device_name == "Test phone"
    assert row.device_id == "device-abc"
    assert row.user_agent == "Test agent"
    assert row.ip_address == "127.0.0.1"
