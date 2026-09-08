from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions.domain_exceptions import (
    DomainError,
    ExpiredVerificationTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidVerificationTokenError,
    UserNotFoundError,
    ValidationError,
)
from app.core.exceptions.http_exceptions import (
    AppException,
    ConflictException,
    ExpiredVerificationTokenException,
    InvalidVerificationTokenException,
    NotFoundException,
    UnauthorizedException,
)

DOMAIN_HTTP_MAPPINGS: dict[type[DomainError], type[AppException]] = {
    UserNotFoundError: NotFoundException,
    InvalidCredentialsError: UnauthorizedException,
    InvalidRefreshTokenError: UnauthorizedException,
    ValidationError: ConflictException,
    InvalidVerificationTokenError: InvalidVerificationTokenException,
    ExpiredVerificationTokenError: ExpiredVerificationTokenException,
}


def error_response(status_code: int, detail: str, **kwargs) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"detail": detail, "status_code": status_code, **kwargs}},
    )


async def domain_exception_handler(request: Request, exc: DomainError) -> JSONResponse:

    if isinstance(exc, ValidationError):
        return error_response(
            status_code=ConflictException.status_code,
            detail=ConflictException.detail,
            fields=exc.fields,
        )

    http_exc_class = DOMAIN_HTTP_MAPPINGS.get(type(exc))

    if http_exc_class is None:
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    http_exc = http_exc_class(detail=str(exc))
    return error_response(
        status_code=http_exc.status_code,
        detail=http_exc.detail,
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return error_response(status_code=exc.status_code, detail=exc.detail)


async def unauthorized_exception_handler(request: Request, exc) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=exc.detail,
        headers=exc.headers,
    )


async def forbidden_exception_handler(request: Request, exc) -> JSONResponse:
    return error_response(status_code=status.HTTP_403_FORBIDDEN, detail=exc.detail)


async def not_found_exception_handler(request: Request, exc) -> JSONResponse:
    return error_response(status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail)


async def conflict_exception_handler(request: Request, exc) -> JSONResponse:
    return error_response(status_code=status.HTTP_409_CONFLICT, detail=exc.detail)


async def field_conflict_exception_handler(request: Request, exc) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_409_CONFLICT,
        detail=exc.detail,
        fields=exc.fields,
    )


async def invalid_verification_token_exception_handler(
    request: Request, exc
) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=exc.detail,
    )


async def expired_verification_token_exception_handler(
    request: Request, exc
) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=exc.detail,
    )
