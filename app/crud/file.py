"""CRUD operations for File model."""

import hashlib
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.base import CRUDBase
from app.models.file import File
from app.schemas.file import FileResponse
from app.services.thumbnail import generate_all_thumbnails, is_image_mime
from app.storage.base import StorageBackend


class CRUDFile(CRUDBase[File, Any, Any]):
    """CRUD operations for uploaded files."""

    async def create_from_upload(
        self,
        db: AsyncSession,
        *,
        file_bytes: bytes,
        original_filename: str,
        mime_type: str,
        storage_path: str,
        uploader_id: int | None,
        storage: StorageBackend,
    ) -> File:
        """Create a File record, generate thumbnails for images, and store them."""
        checksum = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)

        thumbnail_paths: dict[str, str | None] = {
            "small": None,
            "medium": None,
            "large": None,
        }

        if is_image_mime(mime_type) and settings.THUMBNAIL_SIZES:
            thumbs = await generate_all_thumbnails(file_bytes)
            for size_name, thumb_bytes in thumbs.items():
                thumb_filename = f"thumbnails/{storage_path.rsplit('/', 1)[-1].rsplit('.', 1)[0]}_{size_name}.{settings.THUMBNAIL_FORMAT.lower()}"
                thumb_path = await storage.upload_bytes(thumb_bytes, thumb_filename)
                thumbnail_paths[size_name] = thumb_path

        obj = File(
            filename=storage_path.split("/")[-1],
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            checksum_sha256=checksum,
            uploader_id=uploader_id,
            thumbnail_path_small=thumbnail_paths["small"],
            thumbnail_path_medium=thumbnail_paths["medium"],
            thumbnail_path_large=thumbnail_paths["large"],
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def get_by_checksum(
        self, db: AsyncSession, *, checksum: str
    ) -> File | None:
        """Find a file by its SHA-256 checksum."""
        result = await db.execute(select(File).where(File.checksum_sha256 == checksum))
        return result.scalar_one_or_none()

    async def get_multi_by_uploader(
        self, db: AsyncSession, *, uploader_id: int, page: int = 1, per_page: int = 20
    ) -> tuple[list[File], int]:
        """Get files uploaded by a specific user with pagination."""
        count_q = select(func.count()).select_from(
            select(File).where(File.uploader_id == uploader_id).subquery()
        )
        total = (await db.scalar(count_q)) or 0

        q = (
            select(File)
            .where(File.uploader_id == uploader_id)
            .order_by(File.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await db.execute(q)
        return list(result.scalars().all()), total

    def to_response(self, file_obj: File, storage: StorageBackend) -> FileResponse:
        """Convert a File model to a FileResponse with URLs."""
        url = storage.get_url(file_obj.storage_path)
        thumbnail_urls: dict[str, str | None] = {}
        for size_name, path_attr in [
            ("small", "thumbnail_path_small"),
            ("medium", "thumbnail_path_medium"),
            ("large", "thumbnail_path_large"),
        ]:
            path = getattr(file_obj, path_attr, None)
            thumbnail_urls[size_name] = storage.get_url(path) if path else None

        return FileResponse(
            id=file_obj.id,
            filename=file_obj.filename,
            original_filename=file_obj.original_filename,
            mime_type=file_obj.mime_type,
            size_bytes=file_obj.size_bytes,
            storage_path=file_obj.storage_path,
            checksum_sha256=file_obj.checksum_sha256,
            uploader_id=file_obj.uploader_id,
            thumbnail_path_small=file_obj.thumbnail_path_small,
            thumbnail_path_medium=file_obj.thumbnail_path_medium,
            thumbnail_path_large=file_obj.thumbnail_path_large,
            url=url,
            thumbnail_urls=thumbnail_urls if any(thumbnail_urls.values()) else None,
            metadata_=file_obj.metadata_,
            created_at=file_obj.created_at,
            updated_at=file_obj.updated_at,
        )


file = CRUDFile(File)
