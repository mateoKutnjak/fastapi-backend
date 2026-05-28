from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import engine
from app.users import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(router.router, prefix="/users", tags=["users"])
