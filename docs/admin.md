# Admin Dashboard Guide

The project includes an **HTMX‑powered admin dashboard** with real‑time updates, inline editing, live search, SSE task progress, and WebSocket activity feed.

## Access

- URL: `http://localhost:8000/admin`
- Requires an admin role or superuser.

## Features

### Inline Row Editing

Double‑click any cell in the admin table to edit it inline. Changes are sent via PATCH and the cell updates without a page reload.

### Live Search

The search input triggers a server‑side search with a 300ms delay. Only the table body is swapped, keeping the page state.

### Toast Notifications

After creating or updating a record, a green toast notification appears in the top‑right corner.

### Delete Confirmation

Delete links use HTMX’s `hx-confirm` to show a browser confirmation dialog before sending the DELETE request.

### SSE Task Progress

The admin dashboard subscribes to the task‑status SSE endpoint and displays progress bars for background tasks.

### WebSocket Activity Feed

The dashboard connects to the chat WebSocket and displays real‑time activity from the event bus.

### Dark Mode

Toggle dark mode with the button in the navbar. Preference is stored in localStorage.

### Auto‑Registration

Models are registered in `app/admin/__init__.py` using `register_admin()`. Currently enabled models: User, Role, Permission, Tenant, AuditLog.

To add a new model:

```python
from app.admin import register_admin
from app.models import YourModel

register_admin(YourModel, list_display=["column1", "column2"],
               search_columns=["column1"],
               form_fields=["column1", "column2", "column3"],
               permission="your_model:admin")
```

## Profile Page

`/profile` is an HTMX‑powered user profile page with inline editing and avatar upload.

## CDN Dependency

The admin dashboard loads the following libraries from CDN:

- **HTMX** (`unpkg.com/htmx.org@1.9.12`)
- **HTMX extensions** (SSE, WebSocket) from the same CDN
- **Tailwind CSS** (`cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css`)

### Offline / Air‑Gapped Environments

If your deployment environment cannot reach these CDNs, download the files and serve them locally:

1. Download `htmx.min.js` from https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js and place it in `app/admin/static/htmx.min.js`.
2. Download the SSE and WS extensions similarly.
3. Download a compiled Tailwind CSS file or build one locally, and place it in `app/admin/static/tailwind.min.css`.
4. Update the `<script>` and `<link>` tags in `app/admin/templates/base.html` to reference `/admin/static/htmx.min.js` etc.
5. Add a static file mount in `main.py`:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/admin/static", StaticFiles(directory="app/admin/static"), name="admin_static")
```
