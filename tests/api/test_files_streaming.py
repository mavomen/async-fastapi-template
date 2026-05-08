"""Unit tests for the file streaming SSE generator (no HTTP hang)."""

from unittest.mock import AsyncMock

import pytest

from app.api.endpoints.files import _stream_file_upload


@pytest.mark.asyncio
async def test_file_streaming_generator_emits_events():
    """Generator yields start, progress, and complete events."""
    mock_storage = AsyncMock()
    mock_storage.upload.return_value = "path.txt"

    file = AsyncMock()
    file.size = 256
    file.filename = "test.txt"
    file.read = AsyncMock(side_effect=[b"a" * 256, None])
    file.seek = AsyncMock()

    events = []
    async for event in _stream_file_upload(file, file.filename, mock_storage):
        events.append(event)

    assert any("event: start" in e for e in events)
    assert any("event: complete" in e for e in events)
    mock_storage.upload.assert_called_once()
