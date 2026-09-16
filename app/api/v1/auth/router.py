from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.auth import services
from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.api.v1.users.models import User
from app.api.v1.users.schemas import UserCreate, UserLogin
from app.core.db import AsyncSession, get_db
from app.core.email import FastApiMailSender

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: Annotated[UserCreate, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    token_response, raw_token = await services.register_user(body, db)

    fastapi_mail_sender = FastApiMailSender()
    background_tasks.add_task(
        fastapi_mail_sender.send_verification_mail, body.email, raw_token
    )

    return token_response


@router.post("/token", response_model=TokenResponse)
async def token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # TODO change username / email missmatch in OAuth2PasswordRequestForm
    return await services.login_user(
        db, identifier=form_data.username, password=form_data.password
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: Annotated[UserLogin, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await services.login_user(
        db, identifier=body.identifier, password=body.password
    )


@router.post("/logout", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: Annotated[RefreshTokenRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await services.logout_user_from_one_device(db, body.refresh_token)


@router.post("/logout-all", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await services.logout_user_from_all_devices(db, current_user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: Annotated[RefreshTokenRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await services.refresh_token(db, body.refresh_token)


@router.get("/verify")
async def verify_email(
    token: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await services.verify_email(db, token)
    return {"detail": "Email verified successfully"}


@router.post("/oauth/google", response_model=TokenResponse)
async def google_login(
    body: Annotated[GoogleAuthRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await services.google_sign_in(db, body.id_token)


@router.post("/forgot-password", response_model=None)
async def forgot_password(
    body: Annotated[ForgotPasswordRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    raw_token = await services.forgot_password(db, body.email)

    if raw_token is not None:
        fastapi_mail_sender = FastApiMailSender()
        background_tasks.add_task(
            fastapi_mail_sender.send_password_reset_mail, body.email, raw_token
        )

    return {
        "detail": "If an account exists with that email, a reset link has been sent."
    }


@router.post("/reset-password", response_model=None)
async def reset_password(
    body: Annotated[ResetPasswordRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await services.reset_password(db, body)
    return {"detail": "Password has been reset successfully"}


@router.post(
    "/change-password", response_model=None, status_code=status.HTTP_204_NO_CONTENT
)
async def change_password(
    body: Annotated[ChangePasswordRequest, Body()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await services.change_password(db, current_user, body)
