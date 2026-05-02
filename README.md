# async-fastapi-template

Modern async FastAPI template with production-ready patterns.

## Features

- FastAPI with async/await support
- Pydantic v2 settings management
- Health check endpoints (basic, readiness, liveness)
- Structured logging
- Environment-based configuration
- Poetry dependency management
- pytest with async support

## Quick Start

```bash
# Install dependencies
poetry install

# Copy environment template
cp .env.example .env

# Run development server
poetry run uvicorn app.main:app --reload

# Run tests
poetry run pytest
```

## Health Endpoints
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

## Requirements

- Python 3.11+
- Poetry 1.5+

## Project Structure

```
app/
├── api/ # API routes
├── core/ # Core configuration
└── main.py # Application entry
tests/ # Test suite
```

## License

MIT

