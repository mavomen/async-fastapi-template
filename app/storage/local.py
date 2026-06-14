"""Local file system storage backend."""

import asyncio
from pathlib import Path
from typing import BinaryIO

import aiofiles

from app.core.config import settings
from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """Store files on the local disk."""

    def __init__(self) -> None:
        self.storage_path = Path(settings.LOCAL_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: BinaryIO, filename: str) -> str:
        """Save uploaded file to disk and return the relative path."""
        safe_name = Path(filename).name
        file_path = self.storage_path / safe_name
        content = await asyncio.to_thread(file.read)
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)
        return str(file_path.relative_to(self.storage_path))

    async def download(self, path: str) -> bytes:
        """Read file from disk."""
        full_path = self.storage_path / path
        if not full_path.is_file():
            raise FileNotFoundError(f"File {path} not found")
        async with aiofiles.open(full_path, "rb") as f:
            content = await f.read()
            return bytes(content)

    async def delete(self, path: str) -> None:
        """Delete a file from disk."""
        full_path = self.storage_path / path
        if full_path.is_file():
            full_path.unlink()
