# Admin Dashboard Guide

The project includes an **HTMX‑powered admin dashboard** that auto‑discovers registered SQLAlchemy models.

## Access

- URL: `http://localhost:8000/admin`
- Requires an **admin role** or **superuser** flag.

## Auto‑Registration

Models are registered in `app/admin/__init__.py` using `register_admin()`. Currently enabled models:

- User
- Role
- Permission

To add a new model:

```python
from app.admin import register_admin
from app.models import YourModel

register_admin(YourModel, list_display=["column1", "column2"],
               search_columns=["column1"],
               form_fields=["column1", "column2", "column3"],
               permission="your_model:admin")
```

## Features

- List, view, create, edit, and delete records
- Search and pagination
- RBAC‑aware – only users with the required permission can access a model’s admin page
- HTMX‑powered for a smooth SPA‑like experience without JavaScript

## Custom Permissions

Each registered model requires a specific permission (e.g., `user:admin`). Ensure the admin user has this permission assigned via a role.

## Styling

The dashboard uses Tailwind CSS via CDN. You can replace it with your own styles.
