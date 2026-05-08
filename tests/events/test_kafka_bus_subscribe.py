"""Mocked Kafka subscribe/unsubscribe tests."""

from unittest.mock import MagicMock, patch

import pytest

from app.events.base import Event
from app.events.kafka_bus import KafkaEventBus


@pytest.mark.asyncio
async def test_kafka_subscribe_unsubscribe():
    with patch("app.events.kafka_bus.KafkaProducer"), patch(
        "app.events.kafka_bus.KafkaConsumer"
    ):
        bus = KafkaEventBus()
        await bus.connect()

        received = []

        async def handler(e):
            received.append(e)

        await bus.subscribe("test", handler)
        assert "test" in bus._handlers

        await bus.unsubscribe("test", handler)
        assert len(bus._handlers.get("test", [])) == 0

        await bus.close()
