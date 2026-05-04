"""
Test suite for application configuration management.
Tests environment validation, settings behavior, and error handling.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


class TestSettingsBasics:
    """Test basic Settings instantiation and required fields."""

    def test_settings_with_valid_env_vars(self, monkeypatch):
        """Settings should load successfully with all required env vars."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENVIRONMENT", "development")

        settings = Settings()

        assert settings.SECRET_KEY == "a" * 32
        assert settings.ENVIRONMENT == "development"
        assert settings.PROJECT_NAME == "FastAPI Async Template"

    def test_secret_key_required(self, monkeypatch):
        """SECRET_KEY must be provided."""
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "SECRET_KEY" in str(exc_info.value)

    def test_secret_key_minimum_length(self, monkeypatch):
        """SECRET_KEY must be at least 32 characters."""
        monkeypatch.setenv("SECRET_KEY", "short")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "SECRET_KEY" in error_str
        assert "at least 32 characters" in error_str

    def test_secret_key_exactly_32_chars(self, monkeypatch):
        """SECRET_KEY with exactly 32 characters should be valid."""
        secret = "a" * 32
        monkeypatch.setenv("SECRET_KEY", secret)

        settings = Settings()

        assert secret == settings.SECRET_KEY
        assert len(settings.SECRET_KEY) == 32


class TestEnvironmentValidation:
    """Test ENVIRONMENT field validation."""

    @pytest.mark.parametrize("env_value", ["development", "staging", "production", "test"])
    def test_valid_environment_values(self, monkeypatch, env_value):
        """Only specific ENVIRONMENT values should be accepted."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENVIRONMENT", env_value)

        settings = Settings()

        assert env_value == settings.ENVIRONMENT

    @pytest.mark.parametrize(
        "invalid_env",
        ["dev", "prod", "testing", "local", "PRODUCTION", "Development", "invalid"],
    )
    def test_invalid_environment_values(self, monkeypatch, invalid_env):
        """Invalid ENVIRONMENT values should raise ValidationError."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENVIRONMENT", invalid_env)

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "ENVIRONMENT" in error_str

    def test_environment_default_value(self, monkeypatch):
        """ENVIRONMENT should default to 'development'."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        settings = Settings()

        assert settings.ENVIRONMENT == "development"


class TestDatabaseConfiguration:
    """Test DATABASE_URL configuration."""

    def test_database_url_default(self, monkeypatch):
        """DATABASE_URL should have correct default value."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        settings = Settings()

        expected = "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        assert expected == settings.DATABASE_URL

    def test_database_url_custom(self, monkeypatch):
        """DATABASE_URL should accept custom values."""
        custom_url = "postgresql+asyncpg://user:pass@db.example.com:5432/mydb"
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", custom_url)

        settings = Settings()

        assert custom_url == settings.DATABASE_URL

    def test_database_url_with_special_chars(self, monkeypatch):
        """DATABASE_URL should handle special characters in password."""
        url_with_special = "postgresql+asyncpg://user:p@ss%23word@localhost:5432/db"
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", url_with_special)

        settings = Settings()

        assert url_with_special == settings.DATABASE_URL


class TestProjectMetadata:
    """Test project metadata fields."""

    def test_project_name_default(self, monkeypatch):
        """PROJECT_NAME should have correct default."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        settings = Settings()

        assert settings.PROJECT_NAME == "FastAPI Async Template"

    def test_project_name_override(self, monkeypatch):
        """PROJECT_NAME should be overridable via env var."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("PROJECT_NAME", "Custom Project")

        settings = Settings()

        assert settings.PROJECT_NAME == "Custom Project"

    def test_version_default(self, monkeypatch):
        """VERSION should have correct default."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        settings = Settings()

        assert settings.VERSION == "0.1.0"

    def test_version_override(self, monkeypatch):
        """VERSION should be overridable via env var."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("VERSION", "1.2.3")

        settings = Settings()

        assert settings.VERSION == "1.2.3"


class TestAllowedOrigins:
    """Test ALLOWED_ORIGINS CORS configuration."""

    def test_allowed_origins_default(self, monkeypatch):
        """ALLOWED_ORIGINS should have correct default list."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

        settings = Settings()

        expected = ["http://localhost:3000", "http://localhost:8000"]
        assert expected == settings.ALLOWED_ORIGINS

    def test_allowed_origins_single_value(self, monkeypatch):
        """ALLOWED_ORIGINS should accept single origin."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ALLOWED_ORIGINS", '["https://example.com"]')

        settings = Settings()

        assert settings.ALLOWED_ORIGINS == ["https://example.com"]

    def test_allowed_origins_multiple_values(self, monkeypatch):
        """ALLOWED_ORIGINS should accept multiple origins."""
        origins = '["https://app.example.com", "https://admin.example.com"]'
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ALLOWED_ORIGINS", origins)

        settings = Settings()

        assert len(settings.ALLOWED_ORIGINS) == 2
        assert "https://app.example.com" in settings.ALLOWED_ORIGINS
        assert "https://admin.example.com" in settings.ALLOWED_ORIGINS


class TestSettingsImmutability:
    """Test that Settings instances are immutable (frozen)."""

    def test_settings_immutability(self, monkeypatch):
        """Settings fields should not be modifiable after instantiation."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        settings = Settings()

        with pytest.raises((ValidationError, AttributeError)):
            settings.PROJECT_NAME = "Modified"

    def test_settings_immutability_secret_key(self, monkeypatch):
        """SECRET_KEY should not be modifiable after instantiation."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        settings = Settings()

        with pytest.raises((ValidationError, AttributeError)):
            settings.SECRET_KEY = "b" * 32


class TestGetSettingsFunction:
    """Test the get_settings() cached function."""

    def test_get_settings_returns_settings_instance(self, monkeypatch):
        """get_settings() should return a Settings instance."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        get_settings.cache_clear()

        result = get_settings()

        assert isinstance(result, Settings)

    def test_get_settings_caching(self, monkeypatch):
        """get_settings() should return the same instance (cached)."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        get_settings.cache_clear()

        first_call = get_settings()
        second_call = get_settings()

        assert first_call is second_call


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_secret_key(self, monkeypatch):
        """Empty SECRET_KEY should raise ValidationError."""
        monkeypatch.setenv("SECRET_KEY", "")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "SECRET_KEY" in str(exc_info.value)

    def test_whitespace_secret_key(self, monkeypatch):
        """Whitespace-only SECRET_KEY should raise ValidationError."""
        monkeypatch.setenv("SECRET_KEY", " " * 32)

        settings = Settings()
        assert len(settings.SECRET_KEY) == 32

    def test_extra_env_vars_ignored(self, monkeypatch):
        """Extra environment variables should be ignored."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("UNKNOWN_FIELD", "should_be_ignored")

        settings = Settings()

        assert not hasattr(settings, "UNKNOWN_FIELD")

    def test_case_sensitive_env_vars(self, monkeypatch):
        """Environment variables should be case-sensitive."""
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("secret_key", "b" * 32)

        settings = Settings()

        assert settings.SECRET_KEY == "a" * 32
