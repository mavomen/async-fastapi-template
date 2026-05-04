# Deployment Guide

The project includes CI/CD workflows for building Docker images and deploying to a server.

## Docker Image

On every push to `main` or a `v*` tag, a production image is built and pushed to **GitHub Container Registry** (ghcr.io).

### Using the image

```bash
docker pull ghcr.io/<your-org>/async-fastapi-template:main
```

### Automatic Deployment

The deploy.yml workflow triggers after a successful build. It connects to your server via SSH and restarts the app with Docker Compose.

Required Secrets

- SSH_HOST
- SSH_USER
- SSH_PRIVATE_KEY

Set these in your repository’s Settings → Secrets and variables → Actions.

## Production Dockerfile

Dockerfile.prod is a multi‑stage build that copies only production dependencies and the app source. It uses poetry for dependency installation and runs uvicorn as the entry point.

Manual Deployment

```bash
# On your server
docker compose -f docker-compose.prod.yml up -d
```

## Platforms

Adapt the deploy workflow for:

- AWS ECS / Fargate – push to ECR and update service.

- Kubernetes – use kubectl set image or Helm.
