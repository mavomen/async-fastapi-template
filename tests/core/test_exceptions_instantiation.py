"""Trivial tests for custom exception classes."""

from app.core.exceptions import (
    AppException,
    BadRequestException,
    ConflictException,
    ForbiddenException,
    InternalServerException,
    NotFoundException,
    UnauthorizedException,
)


def test_not_found_exception():
    exc = NotFoundException()
    assert exc.status_code == 404


def test_bad_request_exception():
    exc = BadRequestException()
    assert exc.status_code == 400


def test_unauthorized_exception():
    exc = UnauthorizedException()
    assert exc.status_code == 401


def test_forbidden_exception():
    exc = ForbiddenException()
    assert exc.status_code == 403


def test_conflict_exception():
    exc = ConflictException()
    assert exc.status_code == 409


def test_internal_server_exception():
    exc = InternalServerException()
    assert exc.status_code == 500


def test_app_exception_custom_detail():
    exc = AppException(418, "I'm a teapot")
    assert exc.status_code == 418
    assert exc.detail == "I'm a teapot"
