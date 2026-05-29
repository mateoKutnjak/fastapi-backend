from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth import router as auth_router
from app.core.db import engine
from app.users import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


# * persistAuthorization is set to True to keep the user logged
# * in inside Swagger docs when refreshing the /docs page
app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"persistAuthorization": True})

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(user_router.router, prefix="/api/users", tags=["users"])
