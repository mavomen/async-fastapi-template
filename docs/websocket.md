# WebSocket Usage Guide

WebSocket endpoints are available for real‑time communication.

## Chat Example

- **Endpoint:** `/ws/chat`
- **Authorization:** Pass a valid JWT token as query parameter `?token=...`

### Connecting

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/chat?token=YOUR_JWT");
ws.onmessage = (event) => console.log(event.data);
ws.send("Hello everyone!");
```

## Server Behavior

- On connection, the server authenticates the token and adds the user to the broadcast pool.
- Every received message is broadcast to all connected users.
- On disconnect, the user is removed.

## Implementation

`app/websocket/manager.py` – Connection manager with user‑tracking.
`app/websocket/auth.py` – JWT authentication for WebSocket.
`app/websocket/chat.py` – Example chat endpoint.
Extend the manager to support private rooms or targeted messages as needed.
