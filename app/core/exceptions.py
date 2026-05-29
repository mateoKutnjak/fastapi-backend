from fastapi import HTTPException, status


class FieldConflictException(HTTPException):
    def __init__(self, field: str, message: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={"field": field, "message": message},
        )
