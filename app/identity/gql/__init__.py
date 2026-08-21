from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/playground", response_class=HTMLResponse)
async def htmx_graphql_playground(request: Request) -> Any:
    """HTMX-powered GraphQL playground."""
    return HTMLResponse(
        content="""
    <html>
    <head><script src="https://unpkg.com/htmx.org@1.9.12"></script></head>
    <body>
        <h2>GraphQL Playground (HTMX)</h2>
        <textarea id="query" rows="6" cols="80">{ me { id email } }</textarea><br/>
        <button hx-post="/graphql"
                hx-include="#query"
                hx-target="#result"
                class="bg-blue-500 text-white px-4 py-2 rounded">
            Execute
        </button>
        <pre id="result" class="mt-4 bg-gray-100 p-4"></pre>
    </body>
    </html>
    """
    )
