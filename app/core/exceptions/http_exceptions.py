from fastapi import HTTPException, status

from app.core.exceptions.error_codes import ErrorCode, ErrorDetail


class AppException(HTTPException):
    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = ErrorDetail.INTERNAL_ERROR.value
    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=self.__class__.status_code,
            detail=detail or self.__class__.detail,
        )

    def to_response(self):
        return {"error": {"code": self.code, "detail": self.detail}}


class BadRequestException(AppException):
    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = ErrorDetail.BAD_REQUEST.value
    code: ErrorCode = ErrorCode.BAD_REQUEST


class UnauthorizedException(AppException):
    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = ErrorDetail.UNAUTHORIZED.value
    code: ErrorCode = ErrorCode.UNAUTHORIZED


class ForbiddenException(AppException):
    status_code: int = status.HTTP_403_FORBIDDEN
    detail: str = ErrorDetail.FORBIDDEN.value
    code: ErrorCode = ErrorCode.FORBIDDEN


class NotFoundException(AppException):
    status_code: int = status.HTTP_404_NOT_FOUND
    detail: str = ErrorDetail.NOT_FOUND.value
    code: ErrorCode = ErrorCode.NOT_FOUND


class ConflictException(AppException):
    status_code: int = status.HTTP_409_CONFLICT
    detail: str = ErrorDetail.CONFLICT.value
    code: ErrorCode = ErrorCode.CONFLICT
