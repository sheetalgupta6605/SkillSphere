from datetime import datetime, timezone


async def create_notification(db, user_id: str, title: str, message: str, notification_type: str = "general", related_id: str | None = None, href: str = ""):
    """Persist and publish a notification. Notification failures never break the parent action."""
    if not user_id:
        return None
    preference_key = (
        "interview_reminders" if notification_type == "interview_scheduled" else
        "application_updates" if notification_type == "application_update" else
        "messages" if notification_type == "recruiter_message" else
        "platform_updates"
    )
    try:
        preferences = await db.user_preferences.find_one({"user_id": str(user_id)})
        if preferences and preferences.get(preference_key) is False:
            return None
    except Exception:
        pass
    now = datetime.now(timezone.utc)
    value = {
        "user_id": str(user_id), "title": str(title)[:160], "message": str(message)[:1000],
        "notification_type": str(notification_type)[:40], "type": str(notification_type)[:40],
        "related_id": str(related_id) if related_id else None, "href": str(href)[:500],
        "is_read": False, "created_at": now,
    }
    try:
        result = await db.notifications.insert_one(value)
        value["_id"] = result.inserted_id
        try:
            from app.routers.realtime import publish_notification_event
            await publish_notification_event(str(user_id), value)
        except Exception:
            pass
        return value
    except Exception:
        return None
