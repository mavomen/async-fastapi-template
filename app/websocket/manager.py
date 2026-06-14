"""WebSocket connection manager for broadcasting messages."""

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str) -> None:
        async with self._lock:
            connections = set(self.active_connections.get(user_id, set()))
        dead: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)
        for ws in dead:
            await self.disconnect(ws, user_id)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            snapshot = list(self.active_connections.items())
        dead: list[tuple[str, WebSocket]] = []
        for user_id, connections in snapshot:
            for websocket in connections:
                try:
                    await websocket.send_text(message)
                except Exception:
                    dead.append((user_id, websocket))
        for user_id, ws in dead:
            await self.disconnect(ws, user_id)


manager = ConnectionManager()
