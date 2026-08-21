"""Tests for file upload, metadata tracking, and thumbnail generation."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from app.services.thumbnail import (
    _generate_thumbnail_bytes,
    generate_all_thumbnails,
    generate_thumbnail,
    is_image_mime,
)


def _make_test_image(width: int = 256, height: int = 256, fmt: str = "WEBP") -> bytes:
    """Create a test image in memory."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestIsImageMime:
    def test_image_types(self):
        assert is_image_mime("image/png") is True
        assert is_image_mime("image/jpeg") is True
        assert is_image_mime("image/webp") is True

    def test_non_image_types(self):
        assert is_image_mime("application/pdf") is False
        assert is_image_mime("text/plain") is False
        assert is_image_mime("video/mp4") is False


class TestThumbnailGeneration:
    def test_generate_single_thumbnail(self):
        image_bytes = _make_test_image(512, 512)
        result = _generate_thumbnail_bytes(image_bytes, (64, 64), "WEBP", 85)
        assert isinstance(result, bytes)
        assert len(result) > 0
        img = Image.open(BytesIO(result))
        assert img.width <= 64
        assert img.height <= 64

    def test_generate_thumbnail_preserves_aspect_ratio(self):
        image_bytes = _make_test_image(400, 200)
        result = _generate_thumbnail_bytes(image_bytes, (100, 100), "WEBP", 85)
        img = Image.open(BytesIO(result))
        assert img.width <= 100
        assert img.height <= 100
        assert img.width == 100 and img.height == 50  # 2:1 ratio preserved

    def test_generate_thumbnail_jpeg_converts_rgba(self):
        img = Image.new("RGBA", (128, 128), color=(255, 0, 0, 128))
        buf = BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        result = _generate_thumbnail_bytes(image_bytes, (64, 64), "JPEG", 85)
        img_result = Image.open(BytesIO(result))
        assert img_result.mode == "RGB"

    @pytest.mark.asyncio
    async def test_generate_thumbnail_async(self):
        image_bytes = _make_test_image(256, 256)
        result = await generate_thumbnail(image_bytes, (64, 64))
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_all_thumbnails(self):
        image_bytes = _make_test_image(512, 512)
        results = await generate_all_thumbnails(
            image_bytes,
            sizes={"small": (64, 64), "medium": (256, 256)},
        )
        assert "small" in results
        assert "medium" in results
        assert len(results["small"]) < len(results["medium"])


class TestFileModel:
    def test_file_model_has_required_columns(self):
        from app.models.file import File

        columns = {c.name for c in File.__table__.columns}
        expected = {
            "id",
            "filename",
            "original_filename",
            "mime_type",
            "size_bytes",
            "storage_path",
            "checksum_sha256",
            "uploader_id",
            "thumbnail_path_small",
            "thumbnail_path_medium",
            "thumbnail_path_large",
            "metadata",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_file_in_admin_registry(self):
        from app.admin import _registry

        assert "files" in _registry


class TestFileSchemas:
    def test_file_response_schema(self):
        from datetime import UTC, datetime

        from app.schemas.file import FileResponse

        resp = FileResponse(
            id=1,
            filename="test.webp",
            original_filename="test.webp",
            mime_type="image/webp",
            size_bytes=1024,
            storage_path="test.webp",
            checksum_sha256="abc123",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.id == 1
        assert resp.thumbnail_path_small is None

    def test_file_list_response_schema(self):
        from app.schemas.file import FileListResponse

        resp = FileListResponse(items=[], total=0, page=1, per_page=20)
        assert resp.total == 0


class TestFileCRUD:
    @pytest.mark.asyncio
    async def test_get_by_checksum_not_found(self):
        from app.crud.file import file as crud_file

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await crud_file.get_by_checksum(mock_db, checksum="nonexistent")
        assert result is None

    def test_to_response_builds_urls(self):
        from datetime import UTC, datetime

        from app.crud.file import file as crud_file
        from app.models.file import File

        mock_storage = MagicMock()
        mock_storage.get_url.return_value = "https://cdn.example.com/test.webp"

        file_obj = File(
            id=1,
            filename="test.webp",
            original_filename="test.webp",
            mime_type="image/webp",
            size_bytes=1024,
            storage_path="test.webp",
            checksum_sha256="abc123",
            thumbnail_path_small="thumbs/small.webp",
            thumbnail_path_medium="thumbs/medium.webp",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        resp = crud_file.to_response(file_obj, mock_storage)
        assert resp.url == "https://cdn.example.com/test.webp"
        assert resp.thumbnail_urls is not None
        assert resp.thumbnail_urls["small"] == "https://cdn.example.com/test.webp"
