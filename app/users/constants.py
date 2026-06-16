from enum import StrEnum


class RoleEnum(StrEnum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"


class PermissionEnum(StrEnum):
    USERS_READ = "users:read"
    USERS_LIST = "users:list"
    USERS_DELETE = "users:delete"


ROLE_PERMISSIONS = {
    RoleEnum.SUPERADMIN: [
        PermissionEnum.USERS_READ,
        PermissionEnum.USERS_LIST,
        PermissionEnum.USERS_DELETE,
    ],
    RoleEnum.ADMIN: [PermissionEnum.USERS_READ],
    RoleEnum.USER: [],
}


DEFAULT_ROLE = RoleEnum.USER
