import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import get_current_user, require_permission
from app.core.db import get_db
from app.api.v1.users import services
from app.api.v1.users.models import User
from app.api.v1.users.schemas import UserResponsePrivate

router = APIRouter()


@router.get("/me", response_model=UserResponsePrivate)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


@router.get("/{user_id}", response_model=UserResponsePrivate)
async def get_user(
    user_id: Annotated[uuid.UUID, Path()],
    current_user: Annotated[User, Depends(require_permission("users:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await services.get_user_by_id(db, user_id)


@router.get("/", response_model=list[UserResponsePrivate])
async def get_all_users(
    current_user: Annotated[User, Depends(require_permission("users:list"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await services.get_all_users(db)
