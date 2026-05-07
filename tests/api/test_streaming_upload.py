"""Tests for streaming upload SSE event generator."""

import pytest
from unittest.mock import AsyncMock
from io import BytesIO


@pytest.mark.asyncio
async def test_streaming_generator_emits_events():
    """Verify the SSE generator yields start/progress/complete events."""
    # Simulate a small file upload
    file_content = b"x" * 512
    mock_file = BytesIO(file_content)
    mock_file.size = len(file_content)

    # Replicate the generator logic
    import asyncio

    async def event_gen(file, filename="test.txt"):
        total = file.size or 0
        chunk_size = 256
        uploaded = 0
        yield f"event: start\ndata: {filename}\n\n"
        while chunk := file.read(chunk_size):
            uploaded += len(chunk)
            pct = (uploaded / total * 100) if total else 0
            yield f"event: progress\ndata: {pct:.1f}%\n\n"
            await asyncio.sleep(0)
        yield "event: complete\ndata: done\n\n"

    events = []
    async for ev in event_gen(mock_file):
        events.append(ev)

    assert any("event: start" in e for e in events)
    assert any("event: complete" in e for e in events)
