"""WebSocket connection manager for broadcasting messages."""

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str) -> None:
        dead: list[WebSocket] = []
        for websocket in self.active_connections.get(user_id, set()):
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast(self, message: str) -> None:
        dead: list[tuple[str, WebSocket]] = []
        for user_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    await websocket.send_text(message)
                except Exception:
                    dead.append((user_id, websocket))
        for user_id, ws in dead:
            self.disconnect(ws, user_id)


manager = ConnectionManager()
