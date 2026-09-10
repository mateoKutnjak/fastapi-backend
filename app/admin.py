# app/admin.py
from typing import ClassVar

from fastapi import Request
from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend

from app.api.v1.auth.services import login_user
from app.api.v1.users.constants import PermissionEnum
from app.api.v1.users.models import EmailVerificationToken, Permission, Role, User
from app.api.v1.users.services import get_user_by_id
from app.core.db import AsyncSessionLocal
from app.core.exceptions.domain_exceptions import (
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.core.security import TokenType, verify_token


def has_admin_dashboard_access(user: User) -> bool:
    return any(
        p.name == PermissionEnum.ADMIN_DASHBOARD_ACCESS for p in user.role.permissions
    )


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form["username"], form["password"]

        async with AsyncSessionLocal() as db:
            try:
                token_response = await login_user(
                    db, identifier=username, password=password
                )
            except UserNotFoundError, InvalidCredentialsError:
                return False

            user_id = verify_token(token_response.access_token, TokenType.ACCESS)
            user = await get_user_by_id(db, user_id)

            if not user or not has_admin_dashboard_access(user):
                return False

        request.session.update({"token": token_response.access_token})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")

        if not token:
            return False

        try:
            user_id = verify_token(token, TokenType.ACCESS)
        except InvalidTokenError, ExpiredTokenError:
            return False

        async with AsyncSessionLocal() as db:
            user = await get_user_by_id(db, user_id)

        if user and has_admin_dashboard_access(user):
            return True

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
