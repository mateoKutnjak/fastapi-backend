from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions.domain_exceptions import (
    AuthenticationFailedError,
    CurrentUserAlreadyHasPasswordError,
    CurrentUserHasNoPasswordError,
    DomainError,
    ExpiredPasswordResetTokenError,
    ExpiredVerificationTokenError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    InvalidOAuthTokenError,
    InvalidPasswordResetTokenError,
    InvalidRefreshTokenError,
    InvalidVerificationTokenError,
    OAuthEmailNotProvidedError,
    OAuthEmailNotVerifiedError,
    PermissionDeniedError,
    UserNotFoundError,
    ValidationError,
)
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.exceptions.http_exceptions import (
    AppException,
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)

DOMAIN_HTTP_MAPPINGS: dict[type[DomainError], type[AppException]] = {
    UserNotFoundError: NotFoundException,
    InvalidCredentialsError: UnauthorizedException,
    InvalidRefreshTokenError: UnauthorizedException,
    ValidationError: ConflictException,
    InvalidVerificationTokenError: BadRequestException,
    ExpiredVerificationTokenError: BadRequestException,
    InvalidOAuthTokenError: UnauthorizedException,
    InvalidPasswordResetTokenError: UnauthorizedException,
    ExpiredPasswordResetTokenError: UnauthorizedException,
    OAuthEmailNotProvidedError: UnauthorizedException,
    OAuthEmailNotVerifiedError: UnauthorizedException,
    InvalidCurrentPasswordError: UnauthorizedException,
    CurrentUserHasNoPasswordError: UnauthorizedException,
    CurrentUserAlreadyHasPasswordError: UnauthorizedException,
    PermissionDeniedError: ForbiddenException,
    AuthenticationFailedError: UnauthorizedException,
}


async def domain_exception_handler(request: Request, exc: DomainError) -> JSONResponse:

    http_exc_class = DOMAIN_HTTP_MAPPINGS.get(type(exc))

    if http_exc_class is None:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = ErrorDetail.INTERNAL_ERROR.value
        code = ErrorCode.INTERNAL_ERROR
    else:
        status_code = http_exc_class.status_code
        detail = http_exc_class.detail
        code = exc.code

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "detail": detail,
                "status_code": status_code,
                "code": code,
                "fields": getattr(exc, "fields", None),
            }
        },
    )
