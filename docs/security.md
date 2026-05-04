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

Rate limits (slowapi) protect against brute-force attacks.
