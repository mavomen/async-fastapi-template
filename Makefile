.DEFAULT_GOAL := help

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install:
	poetry install

.PHONY: dev
dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: test
test:
	poetry run pytest --cov=app --cov-report=html

.PHONY: lint
lint:
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy app/

.PHONY: lint-fix
lint-fix:
	poetry run ruff check --fix .
	poetry run ruff format .

.PHONY: migrate
migrate:
	poetry run alembic upgrade head

.PHONY: migration
migration:
	poetry run alembic revision --autogenerate -m "$(msg)"

.PHONY: seed
seed:
	poetry run python scripts/seed.py

.PHONY: docker-up
docker-up:
	docker compose -f docker-compose.dev.yml up -d

.PHONY: docker-down
docker-down:
	docker compose -f docker-compose.dev.yml down

.PHONY: celery
celery:
	poetry run celery -A app.core.celery worker --loglevel=info

.PHONY: setup
setup: install migrate

.PHONY: graphql
graphql:  
	@echo "Opening GraphQL playground at http://localhost:8000/graphql"
	@xdg-open http://localhost:8000/graphql 2>/dev/null || open http://localhost:8000/graphql 2>/dev/null || echo "Visit http://localhost:8000/graphql"

.PHONY: load-test
load-test:
	poetry run locust -f locustfile.py

.PHONY: profile
profile:
	py-spy record -o profile.svg -- poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000

.PHONY: scaffold
scaffold:
	poetry run python scripts/scaffold.py

.PHONY: anonymise-db
anonymise-db:
	poetry run python scripts/anonymise_db.py

.PHONY: verify-env
verify-env:
	poetry run python scripts/verify_env.py
