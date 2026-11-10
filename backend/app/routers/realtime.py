import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import get_database
from app.utils.auth import decode_access_token


router = APIRouter(tags=["Realtime"])


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket, accepted: bool = False):
        if not accepted:
            await websocket.accept()
        self.connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        sockets = self.connections.get(user_id, set())
        sockets.discard(websocket)
        if not sockets:
            self.connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, event: dict):
        stale = []
        for socket in self.connections.get(user_id, set()):
            try:
                await socket.send_json(event)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(user_id, socket)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # Do not let unauthenticated clients hold a socket open indefinitely.
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        if auth_message.get("type") != "auth":
            await websocket.close(code=1008)
            return
        token = str(auth_message.get("token", ""))
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            await websocket.close(code=1008)
            return
        user = await get_database().users.find_one({"_id": ObjectId(user_id), "is_active": True})
        if not user or user.get("account_status", "active") != "active" or payload.get("ver", 0) != user.get("auth_version", 0):
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket, accepted=True)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


async def publish_message_event(recipient_id: str, message: dict):
    await manager.send_to_user(recipient_id, {
        "type": "message",
        "message": {
            "id": str(message.get("_id", "")),
            "sender_id": message.get("sender_id"),
            "recipient_id": recipient_id,
            "body": message.get("body"),
            "created_at": message.get("created_at", datetime.now(timezone.utc)).isoformat(),
        },
    })


async def publish_notification_event(user_id: str, notification: dict):
    await manager.send_to_user(user_id, {
        "type": "notification",
        "notification": {
            "id": str(notification.get("_id", "")),
            "type": notification.get("type"),
            "title": notification.get("title"),
            "message": notification.get("message"),
            "created_at": notification.get("created_at", datetime.now(timezone.utc)).isoformat(),
        },
    })
