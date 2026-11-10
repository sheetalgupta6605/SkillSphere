from datetime import datetime, timezone


async def find_candidate_profile(db, user_id: str):
    profile = await db.candidates.find_one({"user_id": user_id})
    if profile:
        return profile
    # Existing records remain readable while older accounts migrate naturally.
    return await db.candidate_profiles.find_one({"user_id": user_id})


async def update_candidate_profile(db, user_id: str, fields: dict):
    fields = {**fields, "updated_at": datetime.now(timezone.utc)}
    canonical = await db.candidates.find_one({"user_id": user_id})
    legacy = await db.candidate_profiles.find_one({"user_id": user_id})
    if canonical:
        await db.candidates.update_one({"user_id": user_id}, {"$set": fields})
    if legacy:
        await db.candidate_profiles.update_one({"user_id": user_id}, {"$set": fields})
    if not canonical and not legacy:
        await db.candidates.update_one({"user_id": user_id}, {"$set": {"user_id": user_id, **fields}}, upsert=True)
    return await find_candidate_profile(db, user_id)


def serialize_candidate_profile(profile: dict | None):
    if not profile:
        return profile
    result = dict(profile)
    result["id"] = str(result.pop("_id"))
    result["completion"] = profile_completion(result)
    return result


def profile_completion(profile: dict | None):
    profile = profile or {}
    sections = {
        "Full name": bool(str(profile.get("full_name") or "").strip()),
        "Phone number": bool(str(profile.get("phone") or profile.get("contact_number") or "").strip()),
        "Location": bool(str(profile.get("location") or "").strip()),
        "Professional headline": bool(str(profile.get("headline") or "").strip()),
        "About me": bool(str(profile.get("summary") or "").strip()),
        "Skills": bool(profile.get("skills")),
        "Education": bool(profile.get("education")),
        "Work experience": bool(profile.get("experience")),
        "Projects": bool(profile.get("projects")),
    }
    complete = sum(sections.values())
    return {"percentage": round(complete / len(sections) * 100), "sections": sections}
