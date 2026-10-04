import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions.domain_exceptions import (
    AuthenticationFailedError,
    ConflictError,
    CurrentUserAlreadyHasPasswordError,
    CurrentUserHasNoPasswordError,
    DomainError,
    ExpiredPasswordResetTokenError,
    ExpiredVerificationTokenError,
    FileDeleteError,
    FileEmptyError,
    FileInvalidFilenameError,
    FileSaveError,
    FileSizeExceededError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    InvalidOAuthTokenError,
    InvalidPasswordResetTokenError,
    InvalidRefreshTokenError,
    InvalidVerificationTokenError,
    OAuthEmailNotProvidedError,
    OAuthEmailNotVerifiedError,
    PermissionDeniedError,
    StorageBackendNotSupportedError,
    UnsupportedImageFormatError,
    UserNotFoundError,
)
from app.core.exceptions.error_codes import ErrorCode, ErrorDetail
from app.core.exceptions.http_exceptions import (
    AppException,
    BadRequestException,
    ConflictException,
    ContentTooLargeException,
    ForbiddenException,
    InternalErrorException,
    NotFoundException,
    UnauthorizedException,
    UnsupportedMediaTypeException,
)

DOMAIN_HTTP_MAPPINGS: dict[type[DomainError], type[AppException]] = {
    UserNotFoundError: NotFoundException,
    InvalidCredentialsError: UnauthorizedException,
    InvalidRefreshTokenError: UnauthorizedException,
    ConflictError: ConflictException,
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
    UnsupportedImageFormatError: UnsupportedMediaTypeException,
    FileSizeExceededError: ContentTooLargeException,
    FileEmptyError: BadRequestException,
    FileSaveError: InternalErrorException,
    FileDeleteError: InternalErrorException,
    FileInvalidFilenameError: BadRequestException,
    StorageBackendNotSupportedError: InternalErrorException,
}


async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logging.error(
        "Database operation failed",
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "detail": ErrorDetail.INTERNAL_ERROR.value,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "code": ErrorCode.DATABASE_ERROR,
                "fields": None,
            }
        },
    )


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

    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logging.error(
            "Server-side domain error: %s",
            exc.code,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

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


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Validation exception handler.
    This handler is responsible for catching validation errors raised by FastAPI
    when the request data does not conform to the expected schema. It restructures
    the error response to include details about the validation failure, the
    HTTP status code, and the specific fields that caused the error.

    Parameters:
        request (Request): The incoming HTTP request.
        exc (RequestValidationError): The validation error that occurred.

    Returns:
        JSONResponse: The JSON response containing validation error details.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = ErrorDetail.VALIDATION_ERROR.value
    code = ErrorCode.VALIDATION_ERROR

    fields = {}

    for item in exc.errors():
        fields_key = item.get("loc")[-1] if item.get("loc") else None
        if fields_key:
            fields[fields_key] = item.get("type")

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "detail": detail,
                "status_code": status_code,
                "code": code,
                "fields": fields,
            }
        },
    )
