from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_database
from app.database.profiles import find_candidate_profile, profile_completion, serialize_candidate_profile, update_candidate_profile
from app.dependencies import require_role
from app.schemas.candidate import CandidateProfileUpdate


router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


@router.get("/me")
@router.get("/profile")
async def get_profile(user=Depends(require_role("candidate")), db=Depends(get_database)):
    profile = await find_candidate_profile(db, str(user["_id"]))
    return serialize_candidate_profile(profile) or {"user_id": str(user["_id"]), "email": user["email"], "full_name": user["full_name"], "skills": [], "education": [], "experience": [], "projects": [], "completion": profile_completion({"full_name": user["full_name"]})}


@router.put("/me")
@router.put("/profile")
async def update_profile(payload: CandidateProfileUpdate, user=Depends(require_role("candidate")), db=Depends(get_database)):
    profile = payload.model_dump(mode="json", exclude_unset=True)
    profile.pop("email", None)
    if "full_name" in profile:
        profile["full_name"] = profile["full_name"].strip()
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"full_name": profile["full_name"], "updated_at": datetime.now(timezone.utc)}})
    return serialize_candidate_profile(await update_candidate_profile(db, str(user["_id"]), profile))

