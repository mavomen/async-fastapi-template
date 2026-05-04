"""OpenTelemetry tracing configuration."""

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import settings


def setup_tracing(app=None) -> None:
    """Initialize OpenTelemetry. Exporter is skipped in test environment."""
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    # No exporter / background thread in test mode
    if settings.ENVIRONMENT == "test":
        return

    if settings.ENVIRONMENT == "development":
        exporter = ConsoleSpanExporter()
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(  # type: ignore[assignment]
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT or "http://localhost:4318/v1/traces",
        )

    provider.add_span_processor(BatchSpanProcessor(exporter))

    if app:
        FastAPIInstrumentor.instrument_app(app)

    SQLAlchemyInstrumentor().instrument(enable_commenter=True)  # type: ignore[no-untyped-call]
