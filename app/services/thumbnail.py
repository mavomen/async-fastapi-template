"""Thumbnail generation service — Pillow-based, runs in threads to avoid blocking."""

import asyncio
from io import BytesIO
from typing import Any

from app.core.config import settings

_IMAGE_MIME_PREFIXES = ("image/",)


def _generate_thumbnail_bytes(
    image_bytes: bytes,
    size: tuple[int, int],
    fmt: str,
    quality: int,
) -> bytes:
    """Generate a single thumbnail. Runs in a thread — must not be called from async context directly."""
    from PIL import Image

    img = Image.open(BytesIO(image_bytes))
    thumb = img.copy()
    thumb.thumbnail(size, Image.Resampling.LANCZOS)
    if fmt.upper() in ("JPEG", "JPG") and thumb.mode in ("RGBA", "P"):
        thumb = thumb.convert("RGB")
    buf = BytesIO()
    save_kwargs: dict[str, Any] = {"format": fmt}
    if fmt.upper() in ("JPEG", "WEBP", "PNG"):
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    thumb.save(buf, **save_kwargs)
    return buf.getvalue()


def is_image_mime(mime_type: str) -> bool:
    """Check if a MIME type represents an image."""
    return any(mime_type.startswith(p) for p in _IMAGE_MIME_PREFIXES)


async def generate_thumbnail(
    image_bytes: bytes,
    size: tuple[int, int],
    fmt: str | None = None,
    quality: int | None = None,
) -> bytes:
    """Generate a single thumbnail asynchronously."""
    fmt = fmt or settings.THUMBNAIL_FORMAT
    quality = quality or settings.THUMBNAIL_QUALITY
    return await asyncio.to_thread(_generate_thumbnail_bytes, image_bytes, size, fmt, quality)


async def generate_all_thumbnails(
    image_bytes: bytes,
    sizes: dict[str, tuple[int, int]] | None = None,
    fmt: str | None = None,
    quality: int | None = None,
) -> dict[str, bytes]:
    """Generate thumbnails for all configured sizes. Returns {size_name: thumbnail_bytes}."""
    sizes = sizes or settings.THUMBNAIL_SIZES
    fmt = fmt or settings.THUMBNAIL_FORMAT
    quality = quality or settings.THUMBNAIL_QUALITY
    tasks = {
        name: asyncio.to_thread(_generate_thumbnail_bytes, image_bytes, size, fmt, quality)
        for name, size in sizes.items()
    }
    results = {}
    for name, coro in tasks.items():
        results[name] = await coro
    return results
