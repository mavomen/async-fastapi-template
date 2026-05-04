"""Abstract interface for file storage backends."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBackend(ABC):
    """Base class for file storage operations."""

    @abstractmethod
    async def upload(self, file: BinaryIO, filename: str) -> str:
        """Store a file and return the retrieval path/URL."""
        ...

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Retrieve file contents by path."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Remove a stored file."""
        ...
