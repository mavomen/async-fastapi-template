"""Custom exception classes for the application."""


class AppException(Exception):
    """Base application exception with status code, error code, and detail."""

    error_code: str = "APP_ERROR"

    def __init__(self, status_code: int, detail: str = "Application error"):
        self.status_code = status_code
        self.detail = detail


class NotFoundException(AppException):
    error_code: str = "NOT_FOUND"

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(404, detail)


class BadRequestException(AppException):
    error_code: str = "BAD_REQUEST"

    def __init__(self, detail: str = "Bad request"):
        super().__init__(400, detail)


class UnauthorizedException(AppException):
    error_code: str = "UNAUTHORIZED"

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(401, detail)


class ForbiddenException(AppException):
    error_code: str = "FORBIDDEN"

    def __init__(self, detail: str = "Forbidden"):
        super().__init__(403, detail)


class RateLimitException(AppException):
    error_code: str = "RATE_LIMITED"

    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(429, detail)


class ConflictException(AppException):
    error_code: str = "CONFLICT"

    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(409, detail)


class LockedOutException(AppException):
    error_code: str = "LOCKED_OUT"

    def __init__(self, detail: str = "Account is locked due to too many failed login attempts"):
        super().__init__(423, detail)


class InternalServerException(AppException):
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str = "Internal server error"):
        super().__init__(500, detail)
