# docs/docker.md

# Docker Setup and Usage Guide

## Overview

This project uses Docker and Docker Compose for containerized deployment. The setup includes:

- **FastAPI application** (multi-stage build)
- **PostgreSQL 18.3** database
- **Redis 7.4** for caching and Celery
- **Celery Worker** for background tasks
- **Celery Beat** for scheduled tasks

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

## Quick Start

### Production Deployment

```bash
# Build and start all services
docker compose up -d

# View logs
docker compose logs -f app

# Stop services
docker compose down

# Stop and remove volumes
docker compose down -v
```

### Development Environment

```bash
# Start development services (includes Adminer and Redis Commander)
docker compose -f docker compose.dev.yml up -d

# Access services:
# - Adminer (PostgreSQL UI): http://localhost:8080
# - Redis Commander: http://localhost:8081
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=fastapi_db
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Application
APP_PORT=8000
ENVIRONMENT=production
SECRET_KEY=your_secret_key_here
```

### Docker Compose Override

For custom configurations, create `docker compose.override.yml`:

```yaml
version: "3.8"

services:
  app:
environment:
DEBUG: "true"
volumes:
  - ./app:/app/app # Mount source for hot reload
```

## Services

### Application Service

**Container**: `fastapi_app`
**Port**: 8000
**Health Check**: `/health` endpoint

```bash
# View application logs
docker compose logs -f app

# Execute commands in container
docker compose exec app bash

# Run migrations
docker compose exec app alembic upgrade head

# Create new migration
docker compose exec app alembic revision --autogenerate -m "description"
```

### Database Service

**Container**: `fastapi_postgres`
**Port**: 5432
**Image**: postgres:18.3-alpine

```bash
# Access PostgreSQL CLI
docker compose exec db psql -U postgres -d fastapi_db

# Backup database
docker compose exec db pg_dump -U postgres fastapi_db > backup.sql

# Restore database
docker compose exec -T db psql -U postgres fastapi_db < backup.sql
```

### Redis Service

**Container**: `fastapi_redis`
**Port**: 6379
**Image**: redis:7.4-alpine

```bash
# Access Redis CLI
docker compose exec redis redis-cli

# Monitor Redis commands
docker compose exec redis redis-cli MONITOR

# Check Redis info
docker compose exec redis redis-cli INFO
```

### Celery Worker

**Container**: `fastapi_celery_worker`
**Command**: `celery -A app.core.celery worker --loglevel=info`

```bash
# View worker logs
docker compose logs -f celery_worker

# Inspect active tasks
docker compose exec celery_worker celery -A app.core.celery inspect active

# Restart worker
docker compose restart celery_worker
```

### Celery Beat

**Container**: `fastapi_celery_beat`
**Command**: `celery -A app.core.celery beat --loglevel=info`

```bash
# View beat logs
docker compose logs -f celery_beat

# Restart beat scheduler
docker compose restart celery_beat
```

## Dockerfile

### Multi-Stage Build

The Dockerfile uses a two-stage build process:

1. **Builder Stage**: Installs Poetry and dependencies
2. **Runtime Stage**: Copies only necessary files for production

### Build Arguments

```bash
# Build with custom Python version
docker build --build-arg PYTHON_VERSION=3.14.3 -t fastapi-app .

# Build without cache
docker build --no-cache -t fastapi-app .
```

## Development Workflow

### Local Development with Docker

```bash
# Start only database and Redis
docker compose -f docker compose.dev.yml up db redis -d

# Run application locally
poetry run uvicorn app.main:app --reload

# Run tests
poetry run pytest
```

### Hot Reload in Container

Add volume mount in `docker compose.override.yml`:

```yaml
services:
  app:
volumes:
  - ./app:/app/app
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Networking

All services communicate through the `app-network` bridge network:

- **Internal DNS**: Services can reference each other by service name
- **Database URL**: `postgresql+asyncpg://postgres:postgres@db:5432/fastapi_db`
- **Redis URL**: `redis://redis:6379/0`

## Volumes

### Persistent Data

- `postgres_data`: PostgreSQL database files
- `redis_data`: Redis persistence files

### Volume Management

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect fastapi_postgres_data

# Remove unused volumes
docker volume prune
```

## Health Checks

All services include health checks:

```bash
# Check service health
docker compose ps

# View health check logs
docker inspect --format='{{json .State.Health}}' fastapi_app | jq
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs app

# Check container status
docker compose ps

# Rebuild without cache
docker compose build --no-cache app
```

### Database Connection Issues

```bash
# Verify database is healthy
docker compose ps db

# Test connection from app container
docker compose exec app pg_isready -h db -U postgres

# Check environment variables
docker compose exec app env | grep DATABASE
```

### Port Conflicts

```bash
# Change ports in .env file
APP_PORT=8001
POSTGRES_PORT=5433
REDIS_PORT=6380

# Restart services
docker compose down && docker compose up -d
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Limit container resources in docker compose.yml
services:
app:
deploy:
resources:
limits:
cpus: '2'
memory: 2G
```

## Production Considerations

### Security

1. **Use secrets management** for sensitive data
2. **Run containers as non-root user** (already configured)
3. **Enable TLS/SSL** for external connections
4. **Use private networks** for internal communication

### Scaling

```bash
# Scale workers

docker compose up -d --scale celery_worker=3

# Use Docker Swarm or Kubernetes for production orchestration
```

### Monitoring

```bash
# Export logs to external system
docker compose logs -f | tee -a app.log

# Use Prometheus + Grafana for metrics

# Use ELK stack for log aggregation
```

### Backup Strategy

```bash
# Automated backup script

#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec -T db pg_dump -U postgres fastapi_db | gzip > backup_$DATE.sql.gz
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Docker Build

on: [push]

jobs:
build:
runs-on: ubuntu-latest
steps:
  - uses: actions/checkout@v3
  - name: Build Docker image
    run: docker build -t fastapi-app .
  - name: Run tests
    run: docker compose run app pytest
```

## Useful Commands

```bash

# Remove all stopped containers

docker compose rm -f

# View resource usage

docker compose top

# Execute pytest in container

docker compose exec app pytest -v

# Shell into running container

docker compose exec app /bin/bash

# View environment variables

docker compose config

```

## References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [Redis Docker Hub](https://hub.docker.com/_/redis)
