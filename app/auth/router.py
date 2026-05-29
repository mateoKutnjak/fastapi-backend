from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.schemas import TokenResponse
from app.auth.services import login_user, register_user
from app.core.db import AsyncSession, get_db
from app.users.schemas import UserCreate

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(
    body: Annotated[UserCreate, Body()], db: Annotated[AsyncSession, Depends(get_db)]
):
    return await register_user(body, db)


@router.post("/token", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # TODO change username / email missmatch in OAuth2PasswordRequestForm
    return await login_user(db, email=form_data.username, password=form_data.password)

