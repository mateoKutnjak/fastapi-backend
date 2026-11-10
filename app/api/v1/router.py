from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.notifications.router import router as notification_router
from app.api.v1.users.router import router as user_router

router = APIRouter(prefix="/v1")

router.include_router(
    auth_router,
    prefix="/auth",
    tags=["auth"],
)

router.include_router(
    user_router,
    prefix="/users",
    tags=["users"],
)

router.include_router(
    notification_router,
    prefix="/notifications",
    tags=["notifications"],
)
