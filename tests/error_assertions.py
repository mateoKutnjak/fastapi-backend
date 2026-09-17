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


def assert_validation_response(response: Response) -> None:
    body = response.json()
    assert "error" not in body
    assert isinstance(body["detail"], list)
    assert body["detail"]
    for error in body["detail"]:
        assert isinstance(error["loc"], list)
        assert error["loc"]
        assert isinstance(error["msg"], str)
        assert isinstance(error["type"], str)
