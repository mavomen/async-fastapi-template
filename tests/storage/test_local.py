"""Tests for local file storage."""

import io
from unittest.mock import MagicMock

import pytest

from app.storage.local import LocalStorage


@pytest.mark.asyncio
async def test_local_upload_download(tmp_path, monkeypatch):
    # Replace the settings object in the local storage module with a mock
    mock_settings = MagicMock()
    mock_settings.LOCAL_STORAGE_PATH = str(tmp_path)
    monkeypatch.setattr("app.storage.local.settings", mock_settings)

    storage = LocalStorage()
    content = b"hello world"
    file = io.BytesIO(content)
    filename = "test.txt"

    path = await storage.upload(file, filename)
    assert path == "test.txt"
    assert (tmp_path / "test.txt").read_bytes() == content

    downloaded = await storage.download("test.txt")
    assert downloaded == content

    await storage.delete("test.txt")
    assert not (tmp_path / "test.txt").exists()
