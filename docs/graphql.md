# GraphQL Guide

The project includes a **GraphQL** endpoint powered by **Strawberry** with async support.

## Endpoint

- **`/graphql`** – GraphQL endpoint with interactive GraphQL playground.
- WebSocket support for subscriptions at the same URL (upgrade to `graphql-ws` protocol).

## Schema

The schema is defined in `app/gql/schema.py`. It includes:

- **Queries:** `me`, `user(userId: Int!)`
- **Mutations:** `createUser(email: String!, username: String!, password: String!, fullName: String)`, `updateUser(userId: Int!, fullName: String, isActive: Boolean)`
- **Subscriptions:** `userLoggedIn(userId: Int!)` (demo, emits a countdown).

## Authentication

Include a JWT token in the HTTP `Authorization` header as `Bearer <token>`. The `me` query requires authentication; other queries/mutations enforce RBAC permissions using the existing `app.auth.permissions` module.

## Usage

Open `http://localhost:8000/graphql` in a browser to use the interactive playground.

## Adding New Types

1. Create a Strawberry type in `app/gql/types/`.
2. Add resolver methods in the appropriate `*_query.py`, `*_mutation.py`, or `*_subscription.py` files.
3. The resolver receives `info: Info`, from which you can access `info.context` (the `request` and `db` session).

## Under the Hood

- The GraphQL router is a `strawberry.fastapi.GraphQLRouter` mounted at `/graphql`.
- Context is built by `get_gql_context` in `app/api/deps.py`, providing access to the FastAPI request and database session.
