"""Tests for S3 storage using mocks."""

import io
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.storage.s3 import S3Storage


@pytest.mark.asyncio
async def test_s3_upload_download(monkeypatch):
    # Mock settings to avoid frozen Settings error
    mock_settings = MagicMock()
    mock_settings.S3_BUCKET = "test-bucket"
    mock_settings.S3_ENDPOINT_URL = None
    mock_settings.S3_ACCESS_KEY = "key"
    mock_settings.S3_SECRET_KEY = "secret"
    mock_settings.S3_REGION = "us-east-1"
    monkeypatch.setattr("app.storage.s3.settings", mock_settings)

    # Mock aioboto3
    mock_s3_client = AsyncMock()
    mock_session = MagicMock()
    mock_session.client.return_value.__aenter__.return_value = mock_s3_client
    monkeypatch.setattr("app.storage.s3.aioboto3.Session", MagicMock(return_value=mock_session))

    storage = S3Storage()
    file = io.BytesIO(b"test content")

    # Upload
    filename = "s3_test.txt"
    path = await storage.upload(file, filename)
    assert path == filename
    mock_s3_client.upload_fileobj.assert_called_once()

    # Download
    mock_s3_client.get_object.return_value = {
        "Body": AsyncMock(read=AsyncMock(return_value=b"test content"))
    }
    result = await storage.download(filename)
    assert result == b"test content"

    # Delete
    await storage.delete(filename)
    mock_s3_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=filename)
