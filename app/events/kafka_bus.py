"""Kafka adapter for EventBus (optional)."""

import asyncio
import json
import logging

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

from app.events.base import Event, EventBus, EventHandler

logger = logging.getLogger("app.events.kafka")


class KafkaEventBus(EventBus):
    """Kafka-backed event bus (synchronous - wraps async)."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "app.events",
        group_id: str = "app-consumers",
    ):
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._producer: KafkaProducer | None = None
        self._consumer: KafkaConsumer | None = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._consumer_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Initialize producer and consumer."""
        try:
            self._producer = KafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                api_version=(2, 5, 0),
            )
            self._consumer = KafkaConsumer(
                self._topic,
                bootstrap_servers=self._bootstrap_servers,
                group_id=self._group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                api_version=(2, 5, 0),
            )
            logger.info("Kafka event bus connected")
        except NoBrokersAvailable:
            logger.warning("Kafka broker not available - bus will be disabled")

    async def publish(self, event: Event) -> None:
        """Send event to Kafka topic."""
        if self._producer:
            self._producer.send(
                self._topic,
                {
                    "event_type": event.event_type,
                    "payload": event.payload,
                    "id": event.id,
                    "timestamp": event.timestamp,
                },
            )
            self._producer.flush()

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)
        if not self._consumer_task:
            self._consumer_task = asyncio.create_task(self._consume_loop())

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def _consume_loop(self) -> None:
        if not self._consumer:
            return
        loop = asyncio.get_event_loop()
        while True:
            try:
                records = await loop.run_in_executor(None, self._consumer.poll, 1.0)
                for _tp, messages in records.items():
                    for msg in messages:
                        event_data = msg.value
                        event = Event(
                            event_type=event_data["event_type"],
                            payload=event_data["payload"],
                            id=event_data["id"],
                            timestamp=event_data["timestamp"],
                        )
                        handlers = self._handlers.get(event.event_type, [])
                        for handler in handlers:
                            try:
                                await handler(event)
                            except Exception:
                                logger.exception("Handler failed for event %s", event.event_type)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Kafka consumer loop error")
                await asyncio.sleep(1)

    async def close(self) -> None:
        if self._consumer_task:
            self._consumer_task.cancel()
            self._consumer_task = None
        if self._consumer:
            self._consumer.close()
        if self._producer:
            self._producer.close()
