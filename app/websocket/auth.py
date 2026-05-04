"""WebSocket authentication dependency."""

from fastapi import WebSocket, WebSocketDisconnect, status

from app.core.database import sessionmanager
from app.core.security import decode_access_token
from app.crud.user import user as crud_user


async def get_current_user_ws(websocket: WebSocket) -> int:
    """Authenticate a WebSocket connection and return user_id."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

    payload = decode_access_token(token)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

    async with sessionmanager.session() as db:
        user = await crud_user.get(db, id=int(user_id))
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

    return int(user_id)
