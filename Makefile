.DEFAULT_GOAL := help

.PHONY: help
help:
	@poetry run python app/cli.py --help

.PHONY: install
install:
	poetry run python app/cli.py install

.PHONY: dev
dev:
	poetry run python app/cli.py dev

.PHONY: test
test:
	poetry run python app/cli.py test

.PHONY: lint
lint:
	poetry run python app/cli.py lint

.PHONY: lint-fix
lint-fix:
	poetry run python app/cli.py lint --fix

.PHONY: migrate
migrate:
	poetry run python app/cli.py migrate

.PHONY: migration
migration:
	poetry run python app/cli.py migrate --message "$(msg)"

.PHONY: seed
seed:
	poetry run python app/cli.py seed

.PHONY: docker-up
docker-up:
	poetry run python app/cli.py docker --up

.PHONY: docker-down
docker-down:
	poetry run python app/cli.py docker --down

.PHONY: celery
celery:
	poetry run python app/cli.py celery

.PHONY: graphql
graphql:
	poetry run python app/cli.py graphql

.PHONY: load-test
load-test:
	poetry run python app/cli.py load-test

.PHONY: profile
profile:
	poetry run python app/cli.py profile

.PHONY: scaffold
scaffold:
	poetry run python app/cli.py scaffold

.PHONY: anonymise-db
anonymise-db:
	poetry run python app/cli.py anonymise-db

.PHONY: verify-env
verify-env:
	poetry run python app/cli.py verify-env

.PHONY: setup
setup:
	poetry run python app/cli.py setup
