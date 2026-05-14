class ApiError(Exception):
    status_code = 400
    code = 4000
    message = "api_error"

    def __init__(self, detail: str | None = None, *, code: int | None = None, message: str | None = None, status_code: int | None = None) -> None:
        super().__init__(detail or message or self.message)
        self.detail = detail
        if code is not None:
            self.code = code
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code


class ValidationApiError(ApiError):
    status_code = 400
    code = 4001
    message = "validation_error"


class NotFoundApiError(ApiError):
    status_code = 404
    code = 4041
    message = "not_found"


class ConflictApiError(ApiError):
    status_code = 409
    code = 4091
    message = "conflict"


class UnauthenticatedApiError(ApiError):
    status_code = 401
    code = 4011
    message = "unauthenticated"
