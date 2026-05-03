# Health Check Documentation

The application provides several health check endpoints for monitoring and orchestration.

## Endpoints

| Method | Path                   | Purpose                    |
| ------ | ---------------------- | -------------------------- |
| GET    | `/health`              | Basic health status        |
| GET    | `/health/ready`        | Readiness probe (k8s)      |
| GET    | `/health/live`         | Liveness probe (k8s)       |
| GET    | `/health/dependencies` | Detailed dependency status |

## Response Formats

### Basic Health (`/health`)

```json
{
  "status": "healthy",
  "timestamp": "2025-05-03T12:00:00Z"
}
```

### Readiness (/health/ready)

Checks database and Redis. Returns ready or degraded.

```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected"
}
```

### Liveness (/health/live)

Simple alive check.

```json
{
  "status": "alive",
  "timestamp": "2025-05-03T12:00:00Z"
}
```

### Dependencies (/health/dependencies)

```json
{
  "status": "ok",
  "components": {
    "database": "connected",
    "redis": "connected"
  }
}
```

### Kubernetes Configuration

Use readinessProbe and livenessProbe pointing to these endpoints.
