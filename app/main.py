from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.db import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


# * persistAuthorization is set to True to keep the user logged
# * in inside Swagger docs when refreshing the /docs page
app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"persistAuthorization": True})

app.include_router(v1_router, prefix="/api")
