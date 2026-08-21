"""File upload and download endpoints."""

import asyncio
import hashlib
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi import File as FastAPIFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user, get_db, get_read_db, get_storage
from app.core.config import settings
from app.crud.file import file as crud_file
from app.identity.models.user import User
from app.schemas.file import FileListResponse, FileResponse
from app.services.thumbnail import generate_all_thumbnails, is_image_mime
from app.storage.base import StorageBackend

router = APIRouter()

_MAX_FILE_SIZE_MB = 50


async def _generate_thumbnails(
    file_bytes: bytes,
    mime_type: str,
    storage_path: str,
    storage: StorageBackend,
) -> dict[str, str | None]:
    """Generate and upload thumbnails for image files. Returns thumbnail storage paths."""
    thumbnail_paths: dict[str, str | None] = {
        "small": None,
        "medium": None,
        "large": None,
    }
    if is_image_mime(mime_type) and settings.THUMBNAIL_SIZES:
        thumbs = await generate_all_thumbnails(file_bytes)
        for size_name, thumb_bytes in thumbs.items():
            stem = storage_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            fmt = settings.THUMBNAIL_FORMAT.lower()
            thumb_filename = f"thumbnails/{stem}_{size_name}.{fmt}"
            thumb_path = await storage.upload_bytes(thumb_bytes, thumb_filename)
            thumbnail_paths[size_name] = thumb_path
    return thumbnail_paths


async def _stream_file_upload(
    file: UploadFile, filename: str, storage: StorageBackend
) -> AsyncGenerator[str, None]:
    """Emit SSE events for file upload progress."""
    total_size = file.size or 0
    chunk_size = 1024 * 256  # 256 KB
    uploaded = 0
    chunks: list[bytes] = []
    yield f"event: start\ndata: {filename}\n\n"
    while chunk := await file.read(chunk_size):
        chunks.append(chunk)
        uploaded += len(chunk)
        percentage = (uploaded / total_size * 100) if total_size else 0
        yield f"event: progress\ndata: {percentage:.1f}%\n\n"
        await asyncio.sleep(0.05)
    content = b"".join(chunks)
    path = await storage.upload_bytes(content, filename)
    url = storage.get_url(path)
    data: dict[str, str | dict[str, str]] = {"path": path}
    if url:
        data["url"] = url
    yield f"event: complete\ndata: {data}\n\n"


@router.post(
    "/upload",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
    description="Upload a file (requires authentication). Creates metadata record and generates thumbnails for images.",
)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
) -> FileResponse:
    """Upload a file with metadata tracking and auto-thumbnailing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {_MAX_FILE_SIZE_MB}MB limit")

    mime_type = file.content_type or "application/octet-stream"
    path = await storage.upload_bytes(content, file.filename)
    checksum = hashlib.sha256(content).hexdigest()

    thumbnail_paths = await _generate_thumbnails(content, mime_type, path, storage)

    file_obj = await crud_file.create_from_upload(
        db,
        filename=path.split("/")[-1],
        original_filename=file.filename,
        mime_type=mime_type,
        size_bytes=len(content),
        checksum=checksum,
        storage_path=path,
        uploader_id=current_user.id,
        thumbnail_paths=thumbnail_paths,
    )
    return crud_file.to_response(file_obj, storage)


@router.post(
    "/upload/stream",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file with SSE progress",
)
async def upload_file_stream(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
) -> StreamingResponse:
    """Upload a file with streaming progress via Server-Sent Events."""
    return StreamingResponse(
        _stream_file_upload(file, file.filename or "unnamed", storage),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List uploaded files",
    description="List the authenticated user's uploaded files with pagination.",
)
async def list_files(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
) -> FileListResponse:
    """List files uploaded by the current user."""
    items, total = await crud_file.get_multi_by_uploader(
        db, uploader_id=current_user.id, page=page, per_page=per_page
    )
    return FileListResponse(
        items=[crud_file.to_response(f, storage) for f in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{file_id}",
    response_model=FileResponse,
    summary="Get file metadata",
)
async def get_file(
    file_id: int,
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
) -> FileResponse:
    """Get metadata for a specific file."""
    file_obj = await crud_file.get(db, id=file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")
    return crud_file.to_response(file_obj, storage)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file",
)
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
) -> None:
    """Soft-delete a file and remove from storage."""
    file_obj = await crud_file.get(db, id=file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")
    await storage.delete(file_obj.storage_path)
    if file_obj.thumbnail_path_small:
        await storage.delete(file_obj.thumbnail_path_small)
    if file_obj.thumbnail_path_medium:
        await storage.delete(file_obj.thumbnail_path_medium)
    if file_obj.thumbnail_path_large:
        await storage.delete(file_obj.thumbnail_path_large)
    await crud_file.delete(db, id=file_id)


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
async def download_file(
    filename: str,
    current_user: User = Depends(get_current_user),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    """Download a file by its stored path."""
    try:
        content = await storage.download(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=content, media_type="application/octet-stream")
