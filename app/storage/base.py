"""Abstract interface for file storage backends."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBackend(ABC):
    """Base class for file storage operations."""

    @abstractmethod
    async def upload(self, file: BinaryIO, filename: str) -> str:
        """Store a file and return the retrieval path/URL."""
        ...

    async def upload_bytes(self, data: bytes, filename: str) -> str:
        """Store raw bytes and return the retrieval path/URL."""
        from io import BytesIO

        return await self.upload(BytesIO(data), filename)

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Retrieve file contents by path."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Remove a stored file."""
        ...
