from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from app.api.v1.auth.authentication import UserContext
from app.api.v1.auth.dependencies import (
    get_current_user_context,
    get_optional_user_context,
)
from app.api.v1.notifications import services
from app.api.v1.notifications.schemas import (
    FCMRegisterTokenBody,
    FCMUnregisterTokenBody,
)
from app.core.db import AsyncSession, get_db

router = APIRouter()


@router.post("/push-tokens", status_code=status.HTTP_201_CREATED)
async def register_push_token(
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    user_context: Annotated[UserContext | None, Depends(get_optional_user_context)],
    body: Annotated[FCMRegisterTokenBody, Body()],
):
    return await services.register_push_token(
        db=db, user_context=user_context, token=body.token, fid=body.fid
    )


@router.put("/push-tokens/unlink", status_code=status.HTTP_200_OK)
async def unlink_push_token(
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    user_context: Annotated[UserContext, Depends(get_current_user_context)],
    body: Annotated[FCMUnregisterTokenBody, Body()],
):
    await services.unlink_push_token(db=db, user_context=user_context, fid=body.fid)


@router.delete("/push-tokens", status_code=status.HTTP_204_NO_CONTENT)
async def delete_push_token(
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    user_context: Annotated[UserContext | None, Depends(get_optional_user_context)],
    body: Annotated[FCMUnregisterTokenBody, Body()],
):
    await services.delete_push_token(db=db, user_context=user_context, fid=body.fid)
