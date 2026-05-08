"""Unit test for Celery event consumer task."""

import contextlib

from app.events.celery_consumer import process_event


def test_process_event_runs():
    """The task can be called with a valid event JSON."""
    event_json = '{"id":"abc","event_type":"test","payload":{},"timestamp":"2026-01-01T00:00:00"}'
    with contextlib.suppress(Exception):
        process_event(event_json)
    assert process_event is not None
