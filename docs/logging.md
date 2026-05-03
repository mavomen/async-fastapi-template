# Logging Configuration Guide

The project uses **structlog** for structured logging and **python-json-logger** for JSON output in non‑development environments.

## Configuration

- In **development**, logs are formatted as human‑readable console output.
- In **production/staging**, logs are JSON objects compatible with log aggregators (e.g. ELK, Datadog).

## Middleware

Two logging middlewares are active:

1. **CorrelationIDMiddleware**
   - Reads `X-Correlation-ID` header or generates a UUID.
   - Attaches the ID to the request state and response header.

2. **RequestLoggingMiddleware**
   - Logs every request with method, path, status code, duration, and correlation ID.
   - Uses `structlog` under the hood.

## Custom Logging Context

Use `LogContext` to temporarily bind key‑value pairs to all log messages emitted within a block:

```python
from app.logging.context import LogContext

with LogContext(user_id=42, action="update"):
    logger.info("User update started")
```

## Adding Logs

Import the logger:

```python
import structlog
logger = structlog.get_logger(__name__)
logger.info("Something happened", extra_field="value")
```
