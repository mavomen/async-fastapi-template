"""Custom exception classes for the application."""


class AppException(Exception):
    """Base application exception with status code and detail."""

    def __init__(self, status_code: int, detail: str = "Application error"):
        self.status_code = status_code
        self.detail = detail


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(404, detail)


class BadRequestException(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(400, detail)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(401, detail)


class ForbiddenException(AppException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(403, detail)


class ConflictException(AppException):
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(409, detail)


class LockedOutException(AppException):
    def __init__(self, detail: str = "Account is locked due to too many failed login attempts"):
        super().__init__(423, detail)


class InternalServerException(AppException):
    def __init__(self, detail: str = "Internal server error"):
        super().__init__(500, detail)
