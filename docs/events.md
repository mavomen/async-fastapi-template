# Event‑Driven Architecture Guide

The project includes a pluggable **EventBus** that supports Redis Streams (default) and Kafka.

## Configuration

- `EVENT_BUS_BACKEND` – `redis` (default) or `kafka`
- `EVENT_BUS_REDIS_URL` – optional, falls back to `REDIS_URL`
- `EVENT_BUS_KAFKA_SERVERS` – Kafka bootstrap servers (default `localhost:9092`)

## Publishing Events

Use the dependency injection to obtain the bus, or publish directly:

```python
POST /api/v1/events/publish
{
  "event_type": "user.created",
  "payload": {"user_id": 42}
}
```

## Subscribing to Events

Register an async handler:

```python
from app.events.base import Event, EventBus

async def handle_user_created(event: Event):
    print(f"User created: {event.payload['user_id']}")

await bus.subscribe("user.created", handle_user_created)
```

## Redis Streams

- Uses consumer groups for reliable message delivery.
- Automatically acknowledges processed messages.
- Streams capped at 10,000 messages.

## Kafka Adapter

- Uses kafka-python with standard producer/consumer.

- Requires a running Kafka broker.

- The adapter handles connection failures gracefully (falls back to disabled).

## Celery Integration

The process_event Celery task bridges events to the WebSocket manager, so all connected clients receive a broadcast when an event is published.

## WebSocket Broadcasting

All events published via the bus are automatically broadcast to every WebSocket client (chat‑style). This is done through app/events/websocket_bridge.py.

## Architecture Overview

```
[API / Celery] → EventBus (Redis Streams / Kafka)
                     ↓
              [WebSocket broadcast]
              [Custom handlers]
```
