"""File upload and download endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user, get_storage
from app.models.user import User
from app.storage.base import StorageBackend

router = APIRouter()


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
    description="Upload a file (requires authentication). Returns the stored filename and path.",
    responses={
        201: {"description": "File uploaded successfully"},
        401: {"description": "Not authenticated"},
        400: {"description": "No file provided"},
    },
)
@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
) -> Any:
    """Upload a file (requires authentication)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Optional: validate file size, type here
    path = await storage.upload(file.file, file.filename)
    return {"filename": file.filename, "path": path}


@router.post("/upload/stream", status_code=status.HTTP_201_CREATED)
async def upload_file_stream(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
):
    """Upload a file with streaming progress via Server-Sent Events."""
    import asyncio

    async def event_generator():
        total_size = file.size or 0
        chunk_size = 1024 * 256  # 256 KB
        uploaded = 0
        yield f"event: start\ndata: {file.filename}\n\n"
        while chunk := await file.read(chunk_size):
            uploaded += len(chunk)
            percentage = (uploaded / total_size * 100) if total_size else 0
            yield f"event: progress\ndata: {percentage:.1f}%\n\n"
            await asyncio.sleep(0.05)
        # Rewind file for final storage write
        await file.seek(0)
        path = await storage.upload(file.file, file.filename)
        yield f"event: complete\ndata: {path}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get(
    "/download/{filename:path}",
    summary="Download a file",
    description="Download a previously uploaded file by its stored path. Requires authentication.",
    responses={
        200: {
            "description": "File content",
            "content": {"application/octet-stream": {}},
        },
        401: {"description": "Not authenticated"},
        404: {"description": "File not found"},
    },
)
@router.get("/download/{filename:path}")
async def download_file(
    filename: str,
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
):
    """Download a file by its stored path."""
    try:
        content = await storage.download(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    # Determine media type (basic)
    return Response(content=content, media_type="application/octet-stream")
