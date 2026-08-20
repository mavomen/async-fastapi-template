"""Property-based tests for User schemas using Hypothesis.

These tests verify invariants that must hold for all inputs,
not just hand-picked examples.

Run with:  poetry run pytest tests/property/ --no-cov
"""

from __future__ import annotations

import os
import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-prop-secret-key-minimum-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)
os.environ.setdefault(
    "DATABASE_URL_READER",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)

from app.schemas.user import UserCreate, UserUpdate

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class TestUserCreateSchema:
    @given(
        email=st.emails(),
        username=st.from_regex(r"[a-zA-Z0-9_-]{3,50}", fullmatch=True),
        password=st.text(min_size=8, max_size=100),
    )
    @settings(max_examples=100, suppress_health_check=list(settings().suppress_health_check))
    def test_valid_user_create_always_validates(
        self, email: str, username: str, password: str
    ) -> None:
        user = UserCreate(email=email, username=username, password=password)
        assert "@" in user.email
        assert user.username == username
        assert USERNAME_RE.match(user.username)

    @given(password=st.text(min_size=1, max_size=7))
    @settings(max_examples=50)
    def test_short_password_rejected(self, password: str) -> None:
        with pytest.raises(Exception):
            UserCreate(
                email="test@example.com",
                username="validuser",
                password=password,
            )

    @given(
        username=st.text(min_size=3, max_size=50).filter(
            lambda u: not USERNAME_RE.match(u)
        )
    )
    @settings(max_examples=50)
    def test_invalid_username_rejected(self, username: str) -> None:
        with pytest.raises(Exception):
            UserCreate(
                email="test@example.com",
                username=username,
                password="validpassword",
            )


class TestUserUpdateSchema:
    @given(
        email=st.emails() | st.none(),
        username=st.from_regex(r"[a-zA-Z0-9_-]{3,50}", fullmatch=True) | st.none(),
        full_name=st.text(max_size=100) | st.none(),
    )
    @settings(max_examples=100)
    def test_partial_update_validates(
        self, email: str | None, username: str | None, full_name: str | None
    ) -> None:
        update = UserUpdate(email=email, username=username, full_name=full_name)
        if email is not None:
            assert "@" in update.email
        if username is not None:
            assert USERNAME_RE.match(update.username)

    @given(password=st.text(min_size=1, max_size=7))
    @settings(max_examples=50)
    def test_short_password_rejected_in_update(self, password: str) -> None:
        with pytest.raises(Exception):
            UserUpdate(password=password)


class TestUserEmailNormalization:
    @given(
        local=st.from_regex(r"[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}", fullmatch=True),
        domain=st.from_regex(r"[a-z0-9]{2,63}\.[a-z]{2,63}", fullmatch=True),
    )
    @settings(max_examples=50)
    def test_email_preserved(self, local: str, domain: str) -> None:
        email = f"{local}@{domain}"
        user = UserCreate(
            email=email, username="testuser1", password="validpassword123"
        )
        assert "@" in user.email
        assert user.email.split("@")[1].lower() == domain.lower()
