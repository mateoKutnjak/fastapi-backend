from fastapi import status
from httpx import Response

from app.core.exceptions.error_codes import ErrorCode, ErrorDetail


def assert_error_response(
    response: Response,
    code: ErrorCode,
    detail: ErrorDetail,
    *,
    fields: dict[str, str] | None = None,
) -> None:
    assert response.json() == {
        "error": {
            "status_code": response.status_code,
            "code": code.value,
            "detail": detail.value,
            "fields": fields,
        }
    }


def assert_validation_response(response: Response, fields: dict[str, str]) -> None:
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert_error_response(
        response,
        ErrorCode.VALIDATION_ERROR,
        ErrorDetail.VALIDATION_ERROR,
        fields=fields,
    )
