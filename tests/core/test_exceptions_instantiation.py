"""Trivial tests for custom exception classes."""

from app.core.exceptions import (
    AppException,
    BadRequestException,
    ConflictException,
    ForbiddenException,
    InternalServerException,
    LockedOutException,
    NotFoundException,
    RateLimitException,
    UnauthorizedException,
)


def test_not_found_exception():
    exc = NotFoundException()
    assert exc.status_code == 404
    assert exc.error_code == "NOT_FOUND"


def test_bad_request_exception():
    exc = BadRequestException()
    assert exc.status_code == 400
    assert exc.error_code == "BAD_REQUEST"


def test_unauthorized_exception():
    exc = UnauthorizedException()
    assert exc.status_code == 401
    assert exc.error_code == "UNAUTHORIZED"


def test_forbidden_exception():
    exc = ForbiddenException()
    assert exc.status_code == 403
    assert exc.error_code == "FORBIDDEN"


def test_rate_limit_exception():
    exc = RateLimitException()
    assert exc.status_code == 429
    assert exc.error_code == "RATE_LIMITED"


def test_conflict_exception():
    exc = ConflictException()
    assert exc.status_code == 409
    assert exc.error_code == "CONFLICT"


def test_locked_out_exception():
    exc = LockedOutException()
    assert exc.status_code == 423
    assert exc.error_code == "LOCKED_OUT"


def test_internal_server_exception():
    exc = InternalServerException()
    assert exc.status_code == 500
    assert exc.error_code == "INTERNAL_ERROR"


def test_app_exception_custom_detail():
    exc = AppException(418, "I'm a teapot")
    assert exc.status_code == 418
    assert exc.detail == "I'm a teapot"
    assert exc.error_code == "APP_ERROR"
