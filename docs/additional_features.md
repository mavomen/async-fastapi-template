# Additional Features Guide

## Email Service

The project includes a structured `EmailService` that renders Jinja2 templates and logs emails. To integrate a real SMTP server, replace the `send_email` method with a library like `aiosmtplib`.

### Email Verification

- Use `POST /api/v1/auth/verify-request` (authenticated) to send a verification email.
- The user clicks the link which calls `GET /api/v1/auth/verify-email?token=...` to verify.

Templates are stored in `app/templates/email/`.

## Data Export

### CSV/Excel Export

Users can be exported to CSV or Excel via:

```
GET /api/v1/users/export?format=csv
GET /api/v1/users/export?format=excel
```

Requires `user:read` permission.

Utilities `export_to_csv` and `export_to_excel` can be reused for any data.

## Adding Custom Features

Use these examples as a starting point for your own business logic.
