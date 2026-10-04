import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.authentication import UserContext
from app.api.v1.auth.dependencies import get_current_user_context, require_permission
from app.api.v1.users import services
from app.api.v1.users.schemas import UserResponsePrivate
from app.core.db import get_db

router = APIRouter()


@router.get("/me", response_model=UserResponsePrivate)
async def get_me(
    user_context: Annotated[UserContext, Depends(get_current_user_context)],
):
    return user_context.user


@router.get("/{user_id}", response_model=UserResponsePrivate)
async def get_user(
    user_id: Annotated[uuid.UUID, Path()],
    user_context: Annotated[UserContext, Depends(require_permission("users:read"))],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
):
    return await services.get_user_by_id(db, user_id)


@router.get("/", response_model=list[UserResponsePrivate])
async def get_all_users(
    user_context: Annotated[UserContext, Depends(require_permission("users:list"))],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
):
    return await services.get_all_users(db)


@router.delete("/me", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user_context: Annotated[UserContext, Depends(get_current_user_context)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
):
    await services.delete_user_by_id(db, user_context.user.id)


@router.delete(
    "/{user_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT
)
async def delete_user(
    user_id: Annotated[uuid.UUID, Path()],
    user_context: Annotated[UserContext, Depends(require_permission("users:delete"))],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
):
    await services.delete_user_by_id(db, user_id)


@router.put("/me/avatar", response_model=UserResponsePrivate)
async def update_me_avatar(
    user_context: Annotated[UserContext, Depends(get_current_user_context)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    file: Annotated[UploadFile, File()],
):
    return await services.update_user_avatar(db, user_context.user.id, file)


@router.delete("/me/avatar", response_model=UserResponsePrivate)
async def delete_me_avatar(
    user_context: Annotated[UserContext, Depends(get_current_user_context)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
):
    return await services.delete_user_avatar(db, user_context.user.id)
