import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.users.model import User
from app.users.schemas import UserResponsePrivate
from app.users.services import get_user_by_id

router = APIRouter()


@router.get("/me", response_model=UserResponsePrivate)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


@router.get("/{user_id}", response_model=UserResponsePrivate)
async def get_user(
    user_id: Annotated[uuid.UUID, Path()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await get_user_by_id(db, user_id)
