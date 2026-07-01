from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.db import engine
from app.core.exceptions.domain_exceptions import DomainError
from app.core.exceptions.handlers import (
    app_exception_handler,
    conflict_exception_handler,
    domain_exception_handler,
    field_conflict_exception_handler,
    forbidden_exception_handler,
    not_found_exception_handler,
    unauthorized_exception_handler,
)
from app.core.exceptions.http_exceptions import (
    AppException,
    ConflictException,
    FieldConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


# * persistAuthorization is set to True to keep the user logged
# * in inside Swagger docs when refreshing the /docs page
app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"persistAuthorization": True})

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(UnauthorizedException, unauthorized_exception_handler)
app.add_exception_handler(ForbiddenException, forbidden_exception_handler)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.add_exception_handler(ConflictException, conflict_exception_handler)
app.add_exception_handler(FieldConflictException, field_conflict_exception_handler)

app.add_exception_handler(DomainError, domain_exception_handler)

app.include_router(v1_router, prefix="/api")
