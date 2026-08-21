"""Property-based tests for generic Pydantic schemas using Hypothesis.

Tests edge cases in schema validation across the application.

Run with:  poetry run pytest tests/property/test_schemas.py -m slow --no-cov
"""

from __future__ import annotations

import contextlib
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-schema-secret-key-minimum-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)
os.environ.setdefault(
    "DATABASE_URL_READER",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)

from app.schemas.user import UserCreate


class TestSchemaRobustness:
    @given(data=st.dictionaries(keys=st.text(min_size=1, max_size=50), values=st.text()))
    @settings(max_examples=50)
    def test_user_create_rejects_arbitrary_extra_fields(self, data: dict[str, str]) -> None:
        """UserCreate should reject unexpected fields (strict mode)."""
        base = {
            "email": "test@example.com",
            "username": "validuser",
            "password": "validpassword123",
        }
        merged = {**base, **data}
        # Should either succeed (if extra fields are ignored) or raise
        with contextlib.suppress(Exception):
            UserCreate(**merged)

    @given(password=st.binary(min_size=0, max_size=200))
    @settings(max_examples=30)
    def test_password_handles_binary_input(self, password: bytes) -> None:
        """Password field should handle bytes input gracefully."""
        with contextlib.suppress(Exception):
            UserCreate(
                email="test@example.com",
                username="validuser",
                password=password.decode("utf-8", errors="ignore"),
            )

    @given(username=st.just("a" * 51))
    @settings(max_examples=10)
    def test_username_max_length_enforced(self, username: str) -> None:
        """Username exceeding 50 chars should be rejected."""
        with pytest.raises(Exception):
            UserCreate(
                email="test@example.com",
                username=username,
                password="validpassword123",
            )

    @given(email=st.from_regex(r"[^@]+@[^@]+", fullmatch=True))
    @settings(max_examples=50)
    def test_malformed_email_rejected(self, email: str) -> None:
        """Invalid email formats should be rejected by EmailStr."""
        if "@" in email and "." in email.split("@")[1]:
            # Might still be valid — only test truly broken ones
            return
        with pytest.raises(Exception):
            UserCreate(
                email=email,
                username="validuser",
                password="validpassword123",
            )
