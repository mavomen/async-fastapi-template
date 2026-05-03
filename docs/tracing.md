# Distributed Tracing Guide

The project uses **OpenTelemetry** for distributed tracing.

## Configuration

- **Development**: traces are printed to the console.
- **Production**: traces are exported via OTLP to an endpoint defined by `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4318/v1/traces`).

## Auto‑instrumentation

- **FastAPI**: all HTTP requests are automatically traced.
- **SQLAlchemy**: database queries are traced with SQL comments.

## Custom Spans

Create custom spans in your code:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("my-operation"):
    # do work
```

## Viewing Traces

Console (dev): printed to stdout.

Jaeger / Grafana Tempo: set OTEL_EXPORTER_OTLP_ENDPOINT to your collector.
