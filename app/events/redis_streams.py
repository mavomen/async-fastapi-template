"""Redis Streams implementation of EventBus."""

import asyncio
import logging

import redis.asyncio as aioredis

from app.events.base import Event, EventBus, EventHandler

logger = logging.getLogger("app.events.redis")


class RedisStreamsEventBus(EventBus):
    """Redis Streams-backed event bus with consumer groups."""

    def __init__(
        self, redis_url: str, stream_name: str = "app:events", group_name: str = "app-consumers"
    ):
        self._redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        self._stream = stream_name
        self._group = group_name
        self._handlers: dict[str, list[EventHandler]] = {}
        self._consumer_tasks: list[asyncio.Task] = []

    async def connect(self) -> None:
        """Create consumer group if not exists."""
        try:
            await self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def publish(self, event: Event) -> None:
        """Add event to Redis Stream."""
        data = event.to_json()
        await self._redis.xadd(self._stream, {"event": data}, maxlen=10000)
        logger.debug(
            "Published event to Redis Stream",
            extra={"event_type": event.event_type, "id": event.id},
        )

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a local handler and start a consumer task if not already running."""
        self._handlers.setdefault(event_type, []).append(handler)
        # Start a single consumer loop for all handlers
        if not self._consumer_tasks:
            task = asyncio.create_task(self._consume_loop())
            self._consumer_tasks.append(task)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def _consume_loop(self) -> None:
        """Continuously read from the Redis Stream and dispatch to handlers."""
        while True:
            try:
                results = await self._redis.xreadgroup(
                    self._group, "consumer", {self._stream: ">"}, count=10, block=5000
                )
                for _stream_name, messages in results:
                    for msg_id, fields in messages:
                        event = Event.from_json(fields["event"])
                        handlers = self._handlers.get(event.event_type, [])
                        failed = False
                        for handler in handlers:
                            try:
                                await handler(event)
                            except Exception:
                                logger.exception("Handler failed for event %s", event.event_type)
                                failed = True
                        if not failed:
                            await self._redis.xack(self._stream, self._group, msg_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Consumer loop error")
                await asyncio.sleep(1)

    async def close(self) -> None:
        for task in self._consumer_tasks:
            task.cancel()
        self._consumer_tasks.clear()
        await self._redis.close()
