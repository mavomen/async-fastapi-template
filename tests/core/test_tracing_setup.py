"""Test that tracing setup executes without crash."""

from unittest.mock import patch

from app.core.tracing import setup_tracing


def test_setup_tracing_non_prod():
    with (
        patch("app.core.tracing.TracerProvider") as mock_provider,
        patch("app.core.tracing.BatchSpanProcessor"),
        patch("app.core.tracing.ConsoleSpanExporter"),
        patch("app.core.tracing.FastAPIInstrumentor"),
        patch("app.core.tracing.SQLAlchemyInstrumentor"),
    ):
        setup_tracing()
        mock_provider.assert_called_once()


def test_setup_tracing_sets_resource():
    with (
        patch("app.core.tracing.TracerProvider") as mock_provider,
        patch("app.core.tracing.BatchSpanProcessor"),
        patch("app.core.tracing.ConsoleSpanExporter"),
        patch("app.core.tracing.FastAPIInstrumentor"),
        patch("app.core.tracing.SQLAlchemyInstrumentor"),
    ):
        setup_tracing()
        call_kwargs = mock_provider.call_args
        resource = call_kwargs.kwargs.get("resource") or call_kwargs[1].get("resource")
        assert resource is not None


def test_setup_tracing_skips_exporter_in_test():
    with (
        patch("app.core.tracing.TracerProvider") as mock_provider,
        patch("app.core.tracing.BatchSpanProcessor") as mock_bsp,
    ):
        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "test"
            mock_settings.OTEL_SERVICE_NAME = "test"
            mock_settings.VERSION = "0.0.0"
            mock_settings.OTEL_SAMPLE_RATE = 1.0
            setup_tracing()
            mock_bsp.assert_not_called()
