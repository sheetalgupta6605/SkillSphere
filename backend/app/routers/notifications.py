from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import get_database
from app.dependencies import current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationPreferences(BaseModel):
    application_updates: bool = True
    interview_reminders: bool = True
    messages: bool = True
    platform_updates: bool = True


def serialize_notification(value: dict) -> dict:
    result = dict(value)
    result["id"] = str(result.pop("_id"))
    result.setdefault("notification_type", result.get("type", "general"))
    result.setdefault("type", result["notification_type"])
    return result


@router.get("/me")
@router.get("")
async def list_notifications(unread_only: bool = False, type: str | None = None,
    limit: int = Query(25, ge=1, le=100), skip: int = Query(0, ge=0),
    user=Depends(current_user), db=Depends(get_database)):
    query = {"user_id": str(user["_id"])}
    if unread_only:
        query["is_read"] = False
    if type:
        query["$or"] = [{"notification_type": type}, {"type": type}]
    values = await db.notifications.find(query).sort("created_at", -1).skip(skip).to_list(length=limit)
    return [serialize_notification(value) for value in values]


@router.get("/unread-count")
async def unread_count(user=Depends(current_user), db=Depends(get_database)):
    count = await db.notifications.count_documents({"user_id": str(user["_id"]), "is_read": False})
    return {"count": count}


@router.get("/preferences")
async def get_preferences(user=Depends(current_user), db=Depends(get_database)):
    value = await db.user_preferences.find_one({"user_id": str(user["_id"])}) or {}
    return {key: value.get(key, True) for key in NotificationPreferences.model_fields}


@router.put("/preferences")
async def save_preferences(payload: NotificationPreferences, user=Depends(current_user), db=Depends(get_database)):
    values = payload.model_dump()
    await db.user_preferences.update_one({"user_id": str(user["_id"])}, {"$set": {**values, "user_id": str(user["_id"]), "updated_at": datetime.now(timezone.utc)}}, upsert=True)
    return values


async def mark_read(notification_id: str, user, db):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    result = await db.notifications.update_one({"_id": ObjectId(notification_id), "user_id": str(user["_id"])},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"updated": result.modified_count}


@router.patch("/{notification_id}/read")
async def mark_one_read(notification_id: str, user=Depends(current_user), db=Depends(get_database)):
    return await mark_read(notification_id, user, db)


@router.patch("/read-all")
async def mark_all_read(user=Depends(current_user), db=Depends(get_database)):
    result = await db.notifications.update_many({"user_id": str(user["_id"]), "is_read": False},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}})
    return {"updated": result.modified_count}


# Backward-compatible route used by earlier frontend versions.
@router.put("/read")
async def mark_notifications_read(notification_id: str | None = None, mark_all: bool = False,
    user=Depends(current_user), db=Depends(get_database)):
    if notification_id:
        return await mark_read(notification_id, user, db)
    if not mark_all:
        raise HTTPException(status_code=422, detail="Provide notification_id or mark_all=true")
    return await mark_all_read(user, db)
