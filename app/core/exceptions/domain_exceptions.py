from app.core.exceptions.error_codes import ErrorCode


class DomainError(Exception):
    code: ErrorCode = ErrorCode.INTERNAL_ERROR


class UserNotFoundError(DomainError):
    code = ErrorCode.USER_NOT_FOUND


class InvalidCredentialsError(DomainError):
    code = ErrorCode.INVALID_CREDENTIALS


class InvalidRefreshTokenError(DomainError):
    code = ErrorCode.INVALID_REFRESH_TOKEN


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT_ERROR

    def __init__(self, fields: dict[str, str]):
        self.fields = fields
        super().__init__(self.fields)


class InvalidTokenError(DomainError):
    code = ErrorCode.INVALID_TOKEN


class ExpiredTokenError(DomainError):
    code = ErrorCode.EXPIRED_TOKEN


class InvalidVerificationTokenError(DomainError):
    code = ErrorCode.INVALID_VERIFICATION_TOKEN


class ExpiredVerificationTokenError(DomainError):
    code = ErrorCode.EXPIRED_VERIFICATION_TOKEN


class AccountLinkingError(DomainError):
    code = ErrorCode.ACCOUNT_LINKING_ERROR


class InvalidOAuthTokenError(DomainError):
    code = ErrorCode.INVALID_OAUTH_TOKEN


class RoleNotFoundError(DomainError):
    code = ErrorCode.ROLE_NOT_FOUND

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Role not found: {self.name}")


class InvalidPasswordResetTokenError(DomainError):
    code = ErrorCode.INVALID_PASSWORD_RESET_TOKEN


class ExpiredPasswordResetTokenError(DomainError):
    code = ErrorCode.EXPIRED_PASSWORD_RESET_TOKEN


class OAuthEmailNotProvidedError(DomainError):
    code = ErrorCode.OAUTH_EMAIL_NOT_PROVIDED


class OAuthEmailNotVerifiedError(DomainError):
    code = ErrorCode.OAUTH_EMAIL_NOT_VERIFIED


class InvalidCurrentPasswordError(DomainError):
    code = ErrorCode.INVALID_CURRENT_PASSWORD


class CurrentUserHasNoPasswordError(DomainError):
    code = ErrorCode.CURRENT_USER_HAS_NO_PASSWORD


class CurrentUserAlreadyHasPasswordError(DomainError):
    code = ErrorCode.CURRENT_USER_ALREADY_HAS_PASSWORD


class AuthenticationFailedError(DomainError):
    code = ErrorCode.AUTHENTICATION_FAILED


class PermissionDeniedError(DomainError):
    code = ErrorCode.PERMISSION_DENIED


class UnsupportedImageFormatError(DomainError):
    code = ErrorCode.UNSUPPORTED_IMAGE_FORMAT


class FileSizeExceededError(DomainError):
    code = ErrorCode.FILE_SIZE_EXCEEDED


class FileEmptyError(DomainError):
    code = ErrorCode.EMPTY_FILE


class StorageInvalidFilenameError(DomainError):
    code = ErrorCode.FILE_INVALID_FILENAME


class FileSaveError(DomainError):
    code = ErrorCode.FILE_SAVE_ERROR


class FileDeleteError(DomainError):
    code = ErrorCode.FILE_DELETE_ERROR


class StorageBackendNotSupportedError(DomainError):
    code = ErrorCode.STORAGE_BACKEND_NOT_SUPPORTED


class StorageInvalidSubfolderFormatError(DomainError):
    code = ErrorCode.STORAGE_INVALID_SUBFOLDER_FORMAT


class StorageInvalidFilePathError(DomainError):
    code = ErrorCode.STORAGE_INVALID_FILE_PATH
