"""Example chat WebSocket endpoint."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.manager import manager
from app.websocket.auth import get_current_user_ws

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_endpoint(websocket: WebSocket):
    """Chat WebSocket: authenticate, join, and broadcast messages."""
    user_id = await get_current_user_ws(websocket)
    await manager.connect(websocket, str(user_id))
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"User {user_id}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, str(user_id))
