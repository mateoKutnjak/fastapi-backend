from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer

from app.api.v1.auth.authentication import UserContext, authenticate_access_token
from app.api.v1.auth.schemas import SessionMetadata
from app.core.db import AsyncSession, get_db
from app.core.exceptions.domain_exceptions import (
    AuthenticationFailedError,
    PermissionDeniedError,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_current_user_context(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserContext:
    # * Override the default behavior of OAuth2PasswordBearer to not raise an exception
    # * if no token is provided. Without this line the 401 exception would be raised
    # * with {"details": "Not authenticated"}.

    if token is None:
        raise AuthenticationFailedError()

    return await authenticate_access_token(db, token)


def require_permission(permission: str):
    async def permission_dependency(
        user_context: Annotated[UserContext, Depends(get_current_user_context)],
    ) -> UserContext:
        permissions = [perm.name for perm in user_context.user.role.permissions]

        if permission not in permissions:
            raise PermissionDeniedError()
        return user_context

    return permission_dependency


def get_session_metadata(
    request: Request,
    device_name: Annotated[
        str | None, Header(alias="X-Device-Name", max_length=255)
    ] = None,
    device_id: Annotated[
        str | None, Header(alias="X-Device-ID", max_length=255)
    ] = None,
) -> SessionMetadata:
    user_agent = request.headers.get("user-agent")

    return SessionMetadata(
        device_name=device_name,
        device_id=device_id,
        user_agent=user_agent[:512] if user_agent else None,
        ip_address=request.client.host if request.client else None,
    )
