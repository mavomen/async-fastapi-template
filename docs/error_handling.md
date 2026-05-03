# Error Handling Guide

This project uses custom exception classes, global FastAPI exception handlers, and a request‑logging middleware.

## Custom Exceptions
All custom exceptions inherit from `AppException` and include a `status_code` and `detail`.

- `NotFoundException` → 404
- `BadRequestException` → 400
- `UnauthorizedException` → 401
- `ForbiddenException` → 403
- `ConflictException` → 409
- `InternalServerException` → 500

Raise them in your endpoint logic:

```python
from app.core.exceptions import NotFoundException

@router.get("/items/{item_id}")
async def get_item(item_id: int, db = Depends(get_db)):
    item = await db.get(item_id)
    if not item:
        raise NotFoundException("Item not found")
    return item
```

## Global Handlers
Registered in app/api/error_handlers.py and attached to the app in main.py:

- AppException handler: returns JSON with the given status_code and detail.

- StarletteHTTPException handler (standard HTTP errors).

- RequestValidationError handler: converts Pydantic validation errors into a simplified list.

- Catch‑all Exception handler: returns 500 “Internal server error”.

Error Logging Middleware
`app/middleware/error_logging.py` logs every request’s method, path, status code, and duration. If an exception escapes, it logs the full traceback.

Logs are structured; integrate with your logging framework (see logging guide).
