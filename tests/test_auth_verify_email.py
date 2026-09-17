import datetime

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.auth.models import EmailVerificationToken
from app.api.v1.users.models import User
from app.core.db import AsyncSession
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.security import hash_string
from tests.conftest import API_VERSION
from tests.error_assertions import assert_error_response


@pytest.mark.asyncio
async def test_verify_email_success(
    client: AsyncClient,
    registered_user_with_role,
    mock_send_verification_email,
    db_session,
):
    user = await registered_user_with_role("user")

    _, raw_token = mock_send_verification_email.call_args.args

    response = await client.get(
        f"{API_VERSION}/auth/verify",
        params={"token": raw_token},
    )

    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["detail"] == "Email verified successfully"

    db_user = await db_session.get(User, user["id"])
    await db_session.refresh(db_user)

    assert db_user.is_verified is True

    db_email_verification_token = await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_string(raw_token)
        )
    )
    db_email_verification_token = db_email_verification_token.scalar_one_or_none()
    assert db_email_verification_token is None


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    response = await client.get(
        f"{API_VERSION}/auth/verify",
        params={"token": "not-a-real-token"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert_error_response(
        response, ErrorCode.INVALID_VERIFICATION_TOKEN, ErrorDetail.BAD_REQUEST
    )


@pytest.mark.asyncio
async def test_verify_email_expired_token(
    client: AsyncClient,
    registered_user_with_role,
    mock_send_verification_email,
    db_session: AsyncSession,
):
    await registered_user_with_role("user")

    _, raw_token = mock_send_verification_email.call_args.args
    token_hash = hash_string(raw_token)

    result = await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
    )
    token_row = result.scalar_one()
    token_row.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        seconds=1
    )
    await db_session.flush()

    response = await client.get(
        f"{API_VERSION}/auth/verify",
        params={"token": raw_token},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert_error_response(
        response, ErrorCode.EXPIRED_VERIFICATION_TOKEN, ErrorDetail.BAD_REQUEST
    )
