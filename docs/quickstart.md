# Quickstart Guide

Get a fully functional FastAPI application running in 5 minutes.

## Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Poetry

## Step 1: Clone & Configure

```bash
git clone https://github.com/your-org/async-fastapi-template.git
cd async-fastapi-template
cp .env.example .env
# Edit .env with your desired secrets (or keep defaults for local dev)
```

## Step 2: Start Services

```bash
docker compose -f docker-compose.dev.yml up -d
```

This starts PostgreSQL and Redis. For Prometheus and Grafana, use the production compose file: `docker compose -f docker-compose.yml up -d`.

## Step 3: Install Python Dependencies

```bash
poetry install
```

## Step 4: Run Database Migrations

```bash
poetry run alembic upgrade head
```

## Step 5: Start the API Server

```bash
poetry run uvicorn app.main:app --reload
```

## Step 6: Explore

- **API docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin)

## Next Steps

- Read the [API Documentation](api.md) to understand endpoints.
- Check the [Architecture Decisions](architecture.md) to understand design choices.
- Explore the other guides in the `docs/` folder.
