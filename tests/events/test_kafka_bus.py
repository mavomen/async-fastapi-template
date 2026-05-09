"""Mocked test for Kafka event bus (does not require a real Kafka broker)."""

from unittest.mock import patch

import pytest

from app.events.base import Event
from app.events.kafka_bus import KafkaEventBus


@pytest.mark.asyncio
async def test_kafka_bus_mocked():
    """Test that Kafka bus uses producer correctly."""
    with (
        patch("app.events.kafka_bus.KafkaProducer") as mock_producer,
        patch("app.events.kafka_bus.KafkaConsumer"),
    ):
        bus = KafkaEventBus()
        await bus.connect()

        event = Event(event_type="test", payload={})
        await bus.publish(event)

        mock_producer.return_value.send.assert_called_once()
        await bus.close()
