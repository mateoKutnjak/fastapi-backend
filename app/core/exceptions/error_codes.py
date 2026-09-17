from enum import StrEnum


class ErrorCode(StrEnum):
    INTERNAL_ERROR = "internal_error"

    # Generic HTTP-level codes (app/core/exceptions/http_exceptions.py)
    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"

    # Domain-level codes (app/core/exceptions/domain_exceptions.py)
    USER_NOT_FOUND = "user_not_found"
    INVALID_CREDENTIALS = "invalid_credentials"
    INVALID_REFRESH_TOKEN = "invalid_refresh_token"  # noqa: S105
    VALIDATION_ERROR = "validation_error"
    INVALID_TOKEN = "invalid_token"  # noqa: S105
    EXPIRED_TOKEN = "expired_token"  # noqa: S105
    INVALID_VERIFICATION_TOKEN = "invalid_verification_token"  # noqa: S105
    EXPIRED_VERIFICATION_TOKEN = "expired_verification_token"  # noqa: S105
    ACCOUNT_LINKING_ERROR = "account_linking_error"
    INVALID_OAUTH_TOKEN = "invalid_oauth_token"  # noqa: S105
    ROLE_NOT_FOUND = "role_not_found"
    INVALID_PASSWORD_RESET_TOKEN = "invalid_password_reset_token"  # noqa: S105
    EXPIRED_PASSWORD_RESET_TOKEN = "expired_password_reset_token"  # noqa: S105
    OAUTH_EMAIL_NOT_PROVIDED = "oauth_email_not_provided"
    OAUTH_EMAIL_NOT_VERIFIED = "oauth_email_not_verified"
    INVALID_CURRENT_PASSWORD = "invalid_current_password"  # noqa: S105
    CURRENT_USER_HAS_NO_PASSWORD = "current_user_has_no_password"  # noqa: S105
    CURRENT_USER_ALREADY_HAS_PASSWORD = "current_user_already_has_password"  # noqa: S105
    AUTHENTICATION_FAILED = "authentication_failed"
    PERMISSION_DENIED = "permission_denied"

    # Conflict-level codes
    USERNAME_ALREADY_EXISTS = "username_already_exists"
    EMAIL_ALREADY_EXISTS = "email_already_exists"


class ErrorDetail(StrEnum):
    INTERNAL_ERROR = "Internal server error"
    BAD_REQUEST = "Bad request"
    UNAUTHORIZED = "Unauthorized"
    FORBIDDEN = "Forbidden"
    NOT_FOUND = "Not found"
    CONFLICT = "Conflict"
