import uuid
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.users.constants import DEFAULT_ROLE, RoleEnum
from app.api.v1.users.models import ForgotPasswordToken
from app.core.db import AsyncSession
from tests.conftest import API_VERSION


@pytest.mark.anyio
async def test_forgot_password_existing_user_creates_token_and_returns_generic_message(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user_with_role,
):
    user = await registered_user_with_role(DEFAULT_ROLE)

    with patch(
        "app.core.email.FastApiMailSender.send_password_reset_mail",
    ):
        response = await client.post(
            f"{API_VERSION}/auth/forgot-password", json={"email": user["email"]}
        )

    assert response.status_code == status.HTTP_200_OK  # match your actual status code
    assert "detail" in response.json()

    token_row = await db_session.scalar(
        select(ForgotPasswordToken).where(
            ForgotPasswordToken.user_id == uuid.UUID(user["id"])
        )
    )
    assert token_row is not None
    assert token_row.expires_at is not None


@pytest.mark.anyio
async def test_forgot_password_nonexistent_user_returns_same_response_no_token_created(
    client: AsyncClient, db_session: AsyncSession
):
    response = await client.post(
        f"{API_VERSION}/auth/forgot-password",
        json={"email": "doesnotexist@example.com"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert "detail" in response.json()

    tokens = (await db_session.scalars(select(ForgotPasswordToken))).all()
    assert len(tokens) == 0


@pytest.mark.anyio
async def test_forgot_password_responses_identical_for_existing_and_nonexistent_user(
    client: AsyncClient, registered_user_with_role
):
    user = await registered_user_with_role(RoleEnum.USER)

    with patch("app.core.email.FastApiMailSender.send_password_reset_mail"):
        existing_response = await client.post(
            f"{API_VERSION}/auth/forgot-password", json={"email": user["email"]}
        )

    nonexistent_response = await client.post(
        f"{API_VERSION}/auth/forgot-password", json={"email": "ghost@example.com"}
    )

    # THE core security property of this endpoint
    assert existing_response.status_code == nonexistent_response.status_code
    assert existing_response.json() == nonexistent_response.json()


@pytest.mark.anyio
async def test_forgot_password_email_case_insensitive_finds_user(
    client: AsyncClient, db_session: AsyncSession, registered_user_with_role
):
    user = await registered_user_with_role(RoleEnum.USER)

    with patch("app.core.email.FastApiMailSender.send_password_reset_mail"):
        response = await client.post(
            f"{API_VERSION}/auth/forgot-password", json={"email": user["email"].upper()}
        )

    assert response.status_code == status.HTTP_200_OK

    token_row = await db_session.scalar(
        select(ForgotPasswordToken).where(
            ForgotPasswordToken.user_id == uuid.UUID(user["id"])
        )
    )
    assert token_row is not None
