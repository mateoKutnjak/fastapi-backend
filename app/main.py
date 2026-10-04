from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqladmin import Admin
from sqlalchemy.exc import SQLAlchemyError

from app.admin import (
    AdminAuth,
    EmailVerificationTokenAdmin,
    ForgotPasswordTokenAdmin,
    OAuthAccountAdmin,
    PermissionAdmin,
    RefreshTokenAdmin,
    RoleAdmin,
    UserAdmin,
)
from app.api.v1.router import router as v1_router
from app.config import settings
from app.core.db import engine
from app.core.exceptions.domain_exceptions import DomainError
from app.core.exceptions.handlers import (
    database_exception_handler,
    domain_exception_handler,
    validation_exception_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


# * persistAuthorization is set to True to keep the user logged
# * in inside Swagger docs when refreshing the /docs page
app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"persistAuthorization": True})

# Exception handlers setup

app.add_exception_handler(DomainError, domain_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)

# API routes setup

app.include_router(v1_router, prefix="/api")

# Static files setup

if settings.storage_backend == "local":
    upload_dir = Path(settings.local_storage_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    app.mount(
        settings.local_storage_upload_mount_path,
        StaticFiles(directory=str(upload_dir)),
        name="uploads",
    )

# Admin setup

admin_authentication_backend = AdminAuth(
    secret_key=settings.admin_secret_key.get_secret_value()
)

admin = Admin(app, engine, authentication_backend=admin_authentication_backend)
admin.add_view(UserAdmin)
admin.add_view(PermissionAdmin)
admin.add_view(RoleAdmin)
admin.add_view(EmailVerificationTokenAdmin)
admin.add_view(OAuthAccountAdmin)
admin.add_view(ForgotPasswordTokenAdmin)
admin.add_view(RefreshTokenAdmin)
