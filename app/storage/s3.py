"""S3-compatible storage backend using aioboto3."""

from typing import BinaryIO
from urllib.parse import quote

from app.core.config import settings
from app.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """Store files in an S3 bucket asynchronously."""

    def __init__(self) -> None:
        import aioboto3

        self.bucket = settings.S3_BUCKET
        self.session = aioboto3.Session()
        self.client_kwargs = {
            "endpoint_url": settings.S3_ENDPOINT_URL,
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "region_name": settings.S3_REGION,
        }

    async def upload(self, file: BinaryIO, filename: str) -> str:
        async with self.session.client("s3", **self.client_kwargs) as s3:
            await s3.upload_fileobj(file, self.bucket, filename)
        return filename  # key within bucket

    async def download(self, path: str) -> bytes:
        async with self.session.client("s3", **self.client_kwargs) as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=path)
            body = await response["Body"].read()
            return bytes(body)

    async def delete(self, path: str) -> None:
        async with self.session.client("s3", **self.client_kwargs) as s3:
            await s3.delete_object(Bucket=self.bucket, Key=path)

    def get_url(self, key: str) -> str | None:
        """Return a CDN URL for the given storage key."""
        if not settings.CDN_DOMAIN:
            return None
        return f"https://{settings.CDN_DOMAIN}/{quote(key)}"
