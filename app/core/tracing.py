"""OpenTelemetry tracing configuration."""

from typing import Any

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from app.core.config import settings

_provider: TracerProvider | None = None


def setup_tracing(app: Any = None) -> None:
    """Initialize OpenTelemetry. Exporter is skipped in test environment."""
    global _provider  # noqa: PLW0603

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    sampler = TraceIdRatioBased(settings.OTEL_SAMPLE_RATE)
    provider = TracerProvider(resource=resource, sampler=sampler)
    _provider = provider
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

    SQLAlchemyInstrumentor().instrument(enable_commenter=True)


def shutdown_tracing() -> None:
    """Flush and shut down the TracerProvider on application exit."""
    if _provider is not None:
        _provider.shutdown()
