from enum import StrEnum


class RoleEnum(StrEnum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"


class PermissionEnum(StrEnum):
    USERS_READ = "users:read"
    USERS_LIST = "users:list"
    USERS_DELETE = "users:delete"
    ADMIN_DASHBOARD_ACCESS = "admin_dashboard:access"
    ADMIN_DASHBOARD_CREATE = "admin_dashboard:create"
    ADMIN_DASHBOARD_EDIT = "admin_dashboard:edit"
    ADMIN_DASHBOARD_DELETE = "admin_dashboard:delete"


ROLE_PERMISSIONS = {
    RoleEnum.SUPERADMIN: [
        PermissionEnum.ADMIN_DASHBOARD_ACCESS,
        PermissionEnum.ADMIN_DASHBOARD_CREATE,
        PermissionEnum.ADMIN_DASHBOARD_EDIT,
        PermissionEnum.ADMIN_DASHBOARD_DELETE,
        PermissionEnum.USERS_READ,
        PermissionEnum.USERS_LIST,
        PermissionEnum.USERS_DELETE,
    ],
    RoleEnum.ADMIN: [
        PermissionEnum.USERS_READ,
        PermissionEnum.ADMIN_DASHBOARD_ACCESS,
    ],
    RoleEnum.USER: [],
}


DEFAULT_ROLE = RoleEnum.USER
