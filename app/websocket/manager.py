"""WebSocket connection manager for broadcasting messages."""

from fastapi import WebSocket
from typing import Dict, Set


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str) -> None:
        for websocket in self.active_connections.get(user_id, set()):
            await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        for connections in self.active_connections.values():
            for websocket in connections:
                await websocket.send_text(message)


manager = ConnectionManager()
