from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.auth import services
from app.api.v1.auth.schemas import RefreshTokenRequest, TokenResponse
from app.api.v1.users.schemas import UserCreate
from app.core.db import AsyncSession, get_db

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: Annotated[UserCreate, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await services.register_user(body, db)


@router.post("/token", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # TODO change username / email missmatch in OAuth2PasswordRequestForm
    return await services.login_user(
        db, email=form_data.username, password=form_data.password
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: Annotated[RefreshTokenRequest, Body()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await services.refresh_token(db, body.refresh_token)
