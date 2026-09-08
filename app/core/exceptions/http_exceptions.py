from fastapi import HTTPException, status


class AppException(HTTPException):
    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=self.__class__.status_code,
            detail=detail or self.__class__.detail,
        )

    def to_response(self):
        return {"error": {"code": self.status_code, "detail": self.detail}}


class BadRequestException(AppException):
    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "Bad request"


class UnauthorizedException(AppException):
    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = "Unauthorized"


class ForbiddenException(AppException):
    status_code: int = status.HTTP_403_FORBIDDEN
    detail: str = "Forbidden"


class NotFoundException(AppException):
    status_code: int = status.HTTP_404_NOT_FOUND
    detail: str = "Not found"


class ConflictException(AppException):
    status_code: int = status.HTTP_409_CONFLICT
    detail: str = "Conflict"


class FieldConflictException(ConflictException):
    def __init__(self, detail: str, fields: list[dict[str, str]]):
        super().__init__(detail=detail)
        self.fields = fields

    def to_response(self):
        return {
            "error": {
                "code": self.__class__.status_code,
                "fields": self.fields,
                "detail": self.detail,
            }
        }


class InvalidVerificationTokenException(AppException):
    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "Invalid verification token"


class ExpiredVerificationTokenException(AppException):
    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "Expired verification token"
