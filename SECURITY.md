# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public issue. Send an email to [security@asyncfastapi.dev](mailto:security@asyncfastapi.dev) with details.

We will respond within 48 hours and work with you to resolve the issue promptly.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.x.x   | :white_check_mark: |
| < 3.0.0 | :x:                |

## Security Best Practices

- All passwords are hashed with bcrypt.
- JWT tokens are signed and verified.
- Role‑based permissions control access to endpoints.
- CORS and security headers are applied.
- SQL injection prevention via SQLAlchemy parameterised queries.
- Rate limiting protects against brute‑force attacks.
- Regular dependency updates are performed.
