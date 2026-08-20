## Security Middlewares

The application includes several security layers:

### Security Headers

All responses automatically include:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 0`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`
- `Strict-Transport-Security` (for HTTPS)
- `Permissions-Policy`

### CSRF Protection

State-changing requests (POST/PUT/PATCH/DELETE) require an `X-Requested-With` header. This protects against cross-site request forgery when used with XHR/fetch.

### SQL Injection Prevention

- SQLAlchemy ORM uses parameterised queries.
- A monitoring middleware logs suspicious patterns for auditing.

### XSS Prevention

Use the `sanitize_input` utility to escape user input before rendering.

### CORS

CORS is configured via `ALLOWED_ORIGINS` settings. In production, restrict to your frontend domain.

### Rate Limiting

Rate limits (Redis sliding-window) protect against brute-force attacks.

## WebAuthn / Passkey Authentication

The project supports passwordless authentication using WebAuthn.

### Registration Flow

1. `POST /api/v1/auth/webauthn/register/begin` (authenticated) – generates PublicKeyCredentialCreationOptions.
2. Client creates a credential using the WebAuthn API.
3. `POST /api/v1/auth/webauthn/register/complete` – verifies the credential and stores it.

### Authentication Flow

1. `POST /api/v1/auth/webauthn/login/begin` – provides the user ID (email) and receives PublicKeyCredentialRequestOptions.
2. Client signs the challenge with the registered passkey.
3. `POST /api/v1/auth/webauthn/login/complete` – verifies the signature and returns a JWT access token.

### Configuration

Set these environment variables:

- `WEBAUTHN_RP_ID` (default `localhost`)
- `WEBAUTHN_RP_NAME` (default `FastAPI Async Template`)
- `WEBAUTHN_ORIGIN` (default `http://localhost:8000`)

## Per‑User Rate Limiting

A second rate‑limiting layer uses the authenticated user ID (`sub` claim) as the bucket key. This prevents a single malicious user from exhausting limits for an entire IP range.

## Request ID in Logs & Traces

Every request's correlation ID is automatically injected into structlog context and OpenTelemetry span attributes. This connects logs ↔ traces ↔ metrics out of the box.

## Feature Flags

A lightweight feature‑flag system controls optional features (WebAuthn, GraphQL subscriptions, etc.). Check `app/core/feature_flags.py` for available flags.
