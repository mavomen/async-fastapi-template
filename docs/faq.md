# Frequently Asked Questions

## General

**Q: Why async?**
A: FastAPI is async‑first. Using async SQLAlchemy 2.0 and async Redis allows the server to handle more concurrent connections without blocking, making it ideal for I/O‑bound workloads.

**Q: Can I use this for a production project?**
A: Yes! The template follows best practices and includes production‑ready configurations (Docker, health‑checks, logging, metrics, tracing). Just replace the default secrets.

**Q: Do I need Redis?**
A: Redis is used for caching, rate limiting, and Celery. You can disable these features by not starting the Redis container, but they are recommended for production.

## Setup

**Q: The setup script fails. What should I do?**
A: Ensure Docker is running and you have Python 3.12+ and Poetry installed. Run `make verify-env` to check which services are down.

**Q: How do I reset the database?**
A: Run `make docker-down && make docker-up` to recreate the containers, then `make migrate` to re‑apply migrations.

## Development

**Q: How do I add a new endpoint?**
A: Run `make scaffold` to interactively generate a model, schema, CRUD, endpoint, and test. Then register the router in `app/api/__init__.py` and create a migration with `make migration msg="add new table"`.

**Q: How do I write tests?**
A: Follow the existing patterns in `tests/`. Use `pytest.mark.asyncio` for async tests and the `async_client` fixture. Run `make test` to execute the suite.

**Q: How do I add a new GraphQL type?**
A: Create a Strawberry type in `app/gql/types/`, add resolvers in `app/gql/queries/`, `app/gql/mutations/`, or `app/gql/subscriptions/`, and re‑export in `app/gql/schema.py`.

## Production

**Q: What do I need to change before deploying?**
A: At minimum, set a strong `SECRET_KEY`, configure `ALLOWED_ORIGINS`, and use secure passwords for the database and Redis. Review the `docs/deployment.md` guide.

**Q: How do I enable HTTPS?**
A: The template does not handle TLS. In production, place a reverse proxy (Nginx, Traefik, Caddy) in front of the app that terminates TLS.

## Contributing

**Q: How do I contribute?**
A: Read [CONTRIBUTING.md](CONTRIBUTING.md). Fork the repo, create a branch (`feat/your-feature`), write code + tests, and open a pull request.
