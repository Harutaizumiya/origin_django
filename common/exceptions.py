class ApiError(Exception):
    status_code = 400
    code = "api_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class ValidationApiError(ApiError):
    status_code = 400
    code = "validation_error"


class NotFoundApiError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictApiError(ApiError):
    status_code = 409
    code = "conflict"
