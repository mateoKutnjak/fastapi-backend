# app/admin.py
from datetime import UTC, datetime
from typing import ClassVar

from fastapi import Request
from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import update

from app.api.v1.auth.authentication import authenticate_access_token
from app.api.v1.auth.models import (
    EmailVerificationToken,
    ForgotPasswordToken,
    OAuthAccount,
    Session,
)
from app.api.v1.auth.schemas import SessionMetadata
from app.api.v1.auth.services import login_user
from app.api.v1.users.constants import PermissionEnum
from app.api.v1.users.models import Permission, Role, User
from app.core.db import AsyncSessionLocal
from app.core.exceptions.domain_exceptions import (
    AuthenticationFailedError,
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.core.security import verify_access_token


def has_admin_dashboard_access(user: User) -> bool:
    return any(
        p.name == PermissionEnum.ADMIN_DASHBOARD_ACCESS for p in user.role.permissions
    )


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form["username"], form["password"]

        user_agent = request.headers.get("user-agent")
        metadata = SessionMetadata(
            user_agent=user_agent[:512] if user_agent else None,
            ip_address=request.client.host if request.client else None,
        )

        async with AsyncSessionLocal() as db:
            try:
                token_response = await login_user(
                    db, identifier=username, password=password, metadata=metadata
                )
                user_context = await authenticate_access_token(
                    db, token_response.access_token
                )
            except (
                UserNotFoundError,
                InvalidCredentialsError,
                AuthenticationFailedError,
            ):
                return False

            if not has_admin_dashboard_access(user_context.user):
                return False

            await db.commit()

        request.session.update({"token": token_response.access_token})
        return True

    async def logout(self, request: Request) -> bool:
        access_token = request.session.get("token")

        if not access_token:
            request.session.clear()
            return False

        try:
            user_id, session_id = verify_access_token(access_token)
        except InvalidTokenError, ExpiredTokenError:
            request.session.clear()
            return False

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Session)
                .where(
                    Session.id == session_id,
                    Session.user_id == user_id,
                    Session.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            )
            await db.commit()

        request.session.clear()

        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")

        if not token:
            return False

        try:
            async with AsyncSessionLocal() as db:
                context = await authenticate_access_token(db, token)
                return has_admin_dashboard_access(context.user)
        except AuthenticationFailedError:
            return False


class UserAdmin(ModelView, model=User):
    column_list: ClassVar[list] = [User.id, User.username, User.email, User.is_verified]
    column_searchable_list: ClassVar[list] = [User.username, User.email]

    can_create = False
    can_edit = True
    can_delete = True


class PermissionAdmin(ModelView, model=Permission):
    column_list: ClassVar[list] = [Permission.id, Permission.name]
    column_searchable_list: ClassVar[list] = [Permission.name]

    can_create = True
    can_edit = True
    can_delete = True


class RoleAdmin(ModelView, model=Role):
    column_list: ClassVar[list] = [Role.id, Role.name]
    column_searchable_list: ClassVar[list] = [Role.name]

    can_create = True
    can_edit = True
    can_delete = True


class EmailVerificationTokenAdmin(ModelView, model=EmailVerificationToken):
    column_list: ClassVar[list] = [
        EmailVerificationToken.id,
        "user.email",
        EmailVerificationToken.token_hash,
    ]
    column_searchable_list: ClassVar[list] = [EmailVerificationToken.token_hash]

    can_create = False
    can_edit = False
    can_delete = True


class ForgotPasswordTokenAdmin(ModelView, model=ForgotPasswordToken):
    column_list: ClassVar[list] = [
        ForgotPasswordToken.id,
        "user.email",
        ForgotPasswordToken.token_hash,
    ]
    column_searchable_list: ClassVar[list] = [ForgotPasswordToken.token_hash]

    can_create = False
    can_edit = False
    can_delete = True


class RefreshTokenAdmin(ModelView, model=Session):
    column_list: ClassVar[list] = [
        Session.id,
        "user.email",
        Session.refresh_token_hash,
        Session.expires_at,
        Session.device_name,
        Session.device_id,
        Session.user_agent,
        Session.ip_address,
        Session.revoked_at,
        Session.absolute_expires_at,
    ]
    column_searchable_list: ClassVar[list] = [Session.refresh_token_hash]

    can_create = False
    can_edit = False
    can_delete = True


class OAuthAccountAdmin(ModelView, model=OAuthAccount):
    column_list: ClassVar[list] = [
        OAuthAccount.id,
        "user.email",
        OAuthAccount.provider,
        OAuthAccount.provider_user_id,
    ]
    column_searchable_list: ClassVar[list] = [
        OAuthAccount.provider,
        OAuthAccount.provider_user_id,
    ]

    can_create = False
    can_edit = True
    can_delete = True
