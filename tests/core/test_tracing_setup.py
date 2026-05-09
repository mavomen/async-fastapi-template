"""Test that tracing setup executes without crash."""

from unittest.mock import patch
from app.core.tracing import setup_tracing


def test_setup_tracing_non_prod():
    with patch("app.core.tracing.TracerProvider") as mock_provider, \
         patch("app.core.tracing.BatchSpanProcessor"), \
         patch("app.core.tracing.ConsoleSpanExporter"), \
         patch("app.core.tracing.FastAPIInstrumentor"), \
         patch("app.core.tracing.SQLAlchemyInstrumentor"):
        setup_tracing()
        mock_provider.assert_called_once()
