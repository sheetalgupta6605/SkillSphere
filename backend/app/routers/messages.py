from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_database
from app.dependencies import current_user
from app.services.notifications import create_notification


router = APIRouter(prefix="/api/messages", tags=["Messages"])


class SendMessageRequest(BaseModel):
    recipient_id: str
    body: str = Field(min_length=1, max_length=5000)


def serialize_message(value: dict) -> dict:
    value["id"] = str(value.pop("_id"))
    return value


@router.get("")
async def list_conversations(user=Depends(current_user), db=Depends(get_database)):
    user_id = str(user["_id"])
    values = await db.messages.find(
        {"$or": [{"sender_id": user_id}, {"recipient_id": user_id}]}
    ).sort("created_at", -1).to_list(length=500)
    latest_by_peer = {}
    for value in values:
        peer_id = value["recipient_id"] if value["sender_id"] == user_id else value["sender_id"]
        if peer_id in latest_by_peer:
            continue
        peer = await db.users.find_one({"_id": ObjectId(peer_id)}) if ObjectId.is_valid(peer_id) else None
        latest_by_peer[peer_id] = {
            "peer_id": peer_id,
            "peer_name": peer.get("full_name", "SkillSphere member") if peer else "SkillSphere member",
            "last_message": value["body"],
            "last_message_at": value["created_at"],
            "unread_count": await db.messages.count_documents(
                {"sender_id": peer_id, "recipient_id": user_id, "is_read": False}
            ),
        }
    return list(latest_by_peer.values())


@router.get("/{peer_id}")
async def get_conversation(peer_id: str, user=Depends(current_user), db=Depends(get_database)):
    if not ObjectId.is_valid(peer_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    user_id = str(user["_id"])
    peer = await db.users.find_one({"_id": ObjectId(peer_id)})
    if not peer:
        raise HTTPException(status_code=404, detail="Conversation not found")
    query = {"$or": [
        {"sender_id": user_id, "recipient_id": peer_id},
        {"sender_id": peer_id, "recipient_id": user_id},
    ]}
    values = await db.messages.find(query).sort("created_at", 1).to_list(length=500)
    await db.messages.update_many(
        {"sender_id": peer_id, "recipient_id": user_id, "is_read": False},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}},
    )
    return {
        "peer_id": peer_id,
        "peer_name": peer.get("full_name", "SkillSphere member"),
        "messages": [serialize_message(value) for value in values],
    }


@router.post("", status_code=201)
async def send_message(payload: SendMessageRequest, user=Depends(current_user), db=Depends(get_database)):
    if not ObjectId.is_valid(payload.recipient_id):
        raise HTTPException(status_code=400, detail="Invalid recipient ID")
    sender_id = str(user["_id"])
    if payload.recipient_id == sender_id:
        raise HTTPException(status_code=422, detail="You cannot message yourself")
    recipient = await db.users.find_one({"_id": ObjectId(payload.recipient_id), "is_active": True})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    value = {
        "sender_id": sender_id,
        "recipient_id": payload.recipient_id,
        "body": payload.body.strip(),
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    }
    if not value["body"]:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    result = await db.messages.insert_one(value)
    value["_id"] = result.inserted_id
    await create_notification(db, payload.recipient_id, f"New message from {user.get('full_name', 'SkillSphere member')}", value["body"][:220], "recruiter_message", str(result.inserted_id), "/messages")
    from app.routers.realtime import publish_message_event
    await publish_message_event(payload.recipient_id, value)
    return serialize_message(value)
