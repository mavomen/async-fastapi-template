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
        if dead:
            async with self._lock:
                user_conns = self.active_connections.get(user_id)
                if user_conns:
                    for ws in dead:
                        user_conns.discard(ws)
                    if not user_conns:
                        del self.active_connections[user_id]

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            items = [(uid, set(conns)) for uid, conns in self.active_connections.items()]
        dead: list[tuple[str, WebSocket]] = []

        async def _send(uid: str, ws: WebSocket) -> None:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append((uid, ws))

        tasks = [_send(uid, ws) for uid, conns in items for ws in conns]
        if tasks:
            await asyncio.gather(*tasks)
        if dead:
            async with self._lock:
                for uid, ws in dead:
                    user_conns = self.active_connections.get(uid)
                    if user_conns:
                        user_conns.discard(ws)
                        if not user_conns:
                            del self.active_connections[uid]


manager = ConnectionManager()
