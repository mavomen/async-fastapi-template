#!/usr/bin/env bash
set -e

echo "Setting up development environment..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || {
	echo "Python 3 is required but not installed. Aborting." >&2
	exit 1
}
command -v poetry >/dev/null 2>&1 || {
	echo "Poetry is required but not installed. Aborting." >&2
	exit 1
}
command -v docker >/dev/null 2>&1 || {
	echo "Docker is required but not installed. Aborting." >&2
	exit 1
}

# Create .env if it doesn't exist
if [ ! -f .env ]; then
	cp .env.example .env
	echo "Created .env from .env.example"
fi

# Start Docker services
docker compose -f docker-compose.dev.yml up -d
echo "Waiting for PostgreSQL and Redis to be ready..."

# Poll PostgreSQL until ready
for i in $(seq 1 30); do
	if docker compose exec -T db pg_isready -U postgres 2>/dev/null; then
		echo "PostgreSQL is ready"
		break
	fi
	echo "Waiting for PostgreSQL... ($i/30)"
	sleep 2
done

# Quick Redis check
for i in $(seq 1 15); do
	if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
		echo "Redis is ready"
		break
	fi
	echo "Waiting for Redis... ($i/15)"
	sleep 2
done

# Install Python dependencies
poetry install
echo "Dependencies installed"

# Run migrations
poetry run alembic upgrade head
echo "Database migrated"

# Seed database (optional)
read -p "Seed the database with sample data? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
	poetry run python scripts/seed.py
fi

echo ""
echo "Setup complete! Run 'make dev' to start the server."
echo "   Visit http://localhost:8000/docs for the API docs."
