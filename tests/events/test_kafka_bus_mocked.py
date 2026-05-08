"""Mocked Kafka event bus tests."""

from unittest.mock import patch

import pytest

from app.events.base import Event
from app.events.kafka_bus import KafkaEventBus


@pytest.mark.asyncio
async def test_kafka_bus_connect_publish_subscribe():
    with patch("app.events.kafka_bus.KafkaProducer") as mock_prod, \
         patch("app.events.kafka_bus.KafkaConsumer"):
        bus = KafkaEventBus()
        await bus.connect()

        event = Event(event_type="test", payload={})
        await bus.publish(event)
        mock_prod.return_value.send.assert_called_once()

        received = []
        async def handler(e):
            received.append(e)
        await bus.subscribe("test", handler)
        # Manually trigger the handler to simulate consumption
        await handler(event)
        assert len(received) == 1

        await bus.unsubscribe("test", handler)
        await bus.close()
