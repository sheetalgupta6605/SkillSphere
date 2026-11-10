from calendar import month_abbr
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.database import get_database
from app.database.profiles import find_candidate_profile, profile_completion
from app.dependencies import require_role
from app.services.notifications import create_notification
from app.routers.jobs import active_jobs_query

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class UserStatusUpdate(BaseModel):
    is_active: bool


class JobRejection(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Rejection reason must have at least 5 characters")
        return value


def serialize(value: dict) -> dict:
    result = dict(value)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    return result


def paginate(collection, query: dict, page: int, limit: int, sort_field: str = "created_at"):
    return collection.find(query).sort(sort_field, -1).skip((page - 1) * limit).limit(limit)


@router.get("/dashboard")
async def dashboard(_: dict = Depends(require_role("admin")), db=Depends(get_database)):
    now = datetime.now(timezone.utc)
    user_total = await db.users.count_documents({})
    candidates = await db.users.count_documents({"role": "candidate"})
    recruiters = await db.users.count_documents({"role": "recruiter"})
    companies = await db.companies.count_documents({})
    total_jobs = await db.jobs.count_documents({})
    active = await db.jobs.count_documents(active_jobs_query(now))
    pending = await db.jobs.count_documents({"status": {"$in": ["pending", "pending_approval"]}})
    applications = await db.applications.count_documents({})
    shortlisted = await db.applications.count_documents({"status": "shortlisted"})
    interviews = await db.applications.count_documents({"status": {"$in": ["interview", "interview_scheduled"]}})
    recent_users = await db.users.find({}, {"password_hash": 0, "auth_version": 0, "password_reset_token_hash": 0, "password_reset_expires_at": 0}).sort("created_at", -1).to_list(length=6)
    recent_jobs = await db.jobs.find({}).sort("created_at", -1).to_list(length=6)
    pending_jobs = await db.jobs.find({"status": {"$in": ["pending", "pending_approval"]}}).sort("created_at", -1).to_list(length=6)
    recent_job_ids = {str(job["_id"]): job for job in [*recent_jobs, *pending_jobs]}
    recent_apps = await db.applications.find({}).sort("created_at", -1).to_list(length=8)
    activity = []
    for application in recent_apps:
        job = recent_job_ids.get(application.get("job_id"))
        if not job and ObjectId.is_valid(str(application.get("job_id", ""))):
            job = await db.jobs.find_one({"_id": ObjectId(application["job_id"])}, {"title": 1})
        job = job or {}
        candidate_id = application.get("candidate_id", "")
        user = await db.users.find_one({"_id": ObjectId(candidate_id)}, {"full_name": 1}) if ObjectId.is_valid(candidate_id) else None
        events = application.get("status_history") or [{"status": application.get("status", "submitted"), "at": application.get("created_at")}]
        if events:
            event = events[-1]
            activity.append({"type": "application", "candidate_name": (user or {}).get("full_name", "Candidate"), "job_title": job.get("title", "Job posting"), "status": event.get("new_status") or event.get("status", "submitted"), "at": event.get("at") or application.get("created_at")})
    for user in recent_users:
        activity.append({"type": "registration", "label": f"{user.get('full_name', 'A user')} registered", "at": user.get("created_at")})
    activity.sort(key=lambda item: item.get("at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return {
        "total_users": user_total, "candidates": candidates, "recruiters": recruiters, "companies": companies,
        "total_jobs": total_jobs, "jobs": total_jobs, "active_jobs": active, "pending_jobs": pending,
        "total_applications": applications, "applications": applications, "shortlisted_candidates": shortlisted,
        "interviews_scheduled": interviews,
        "recent_users": [serialize(value) for value in recent_users],
        "recent_jobs": [serialize(value) for value in recent_jobs],
        "pending_approvals": [serialize(value) for value in pending_jobs],
        "recent_activity": activity[:12],
    }


@router.get("/analytics")
async def analytics(user: dict = Depends(require_role("admin")), db=Depends(get_database)):
    return await dashboard(user, db)


@router.get("/reports")
async def reports(_: dict = Depends(require_role("admin")), db=Depends(get_database)):
    now = datetime.now(timezone.utc)
    month_keys = []
    for offset in reversed(range(6)):
        year, month = now.year, now.month - offset
        while month <= 0:
            year -= 1
            month += 12
        month_keys.append((year, month))
    start_year, start_month = month_keys[0]
    start = datetime(start_year, start_month, 1, tzinfo=timezone.utc)
    collections = {"users": db.users, "jobs": db.jobs, "applications": db.applications}
    trends = {}
    for name, collection in collections.items():
        counts = {(year, month): 0 for year, month in month_keys}
        grouped = await collection.aggregate([{"$match": {"created_at": {"$gte": start}}}, {"$group": {"_id": {"year": {"$year": "$created_at"}, "month": {"$month": "$created_at"}}, "count": {"$sum": 1}}}]).to_list(length=12)
        for record in grouped:
            key = (record["_id"]["year"], record["_id"]["month"])
            if key in counts:
                counts[key] = record["count"]
        trends[name] = [{"month": f"{month_abbr[month]} {str(year)[-2:]}", "count": counts[(year, month)]} for year, month in month_keys]
    jobs_total = await db.jobs.count_documents({})
    grouped_statuses = await db.jobs.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]).to_list(length=20)
    job_statuses = {item.get("_id") or "unknown": item["count"] for item in grouped_statuses}
    return {
        "totals": {"users": await db.users.count_documents({}), "candidates": await db.users.count_documents({"role": "candidate"}), "recruiters": await db.users.count_documents({"role": "recruiter"}), "companies": await db.companies.count_documents({}), "jobs": jobs_total, "applications": await db.applications.count_documents({})},
        "job_statuses": job_statuses, "trends": trends,
    }


@router.get("/users")
async def users(search: str | None = Query(default=None, max_length=120), role: str | None = Query(default=None), status: str | None = Query(default=None), page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100), _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    query = {}
    if role in {"candidate", "recruiter", "admin"}:
        query["role"] = role
    if status in {"active", "disabled"}:
        query["is_active"] = status == "active"
    if search and search.strip():
        import re
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [{"full_name": {"$regex": pattern}}, {"email": {"$regex": pattern}}]
    cursor = paginate(db.users, query, page, limit)
    values = await cursor.to_list(length=limit)
    total = await db.users.count_documents(query)
    safe = []
    for value in values:
        for key in ("password_hash", "password", "hashed_password", "auth_version", "password_reset_token_hash", "password_reset_expires_at", "verification_token_hash"):
            value.pop(key, None)
        safe.append(serialize(value))
    return {"items": safe, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/users/{user_id}")
async def user_detail(user_id: str, _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    value = await db.users.find_one({"_id": ObjectId(user_id)})
    if not value:
        raise HTTPException(status_code=404, detail="User not found")
    for key in ("password_hash", "password", "hashed_password", "auth_version", "password_reset_token_hash", "password_reset_expires_at", "verification_token_hash"):
        value.pop(key, None)
    return serialize(value)


@router.patch("/users/{user_id}/status")
@router.put("/users/{user_id}/status")
async def update_user_status(user_id: str, payload: UserStatusUpdate, user: dict = Depends(require_role("admin")), db=Depends(get_database)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    target_id = ObjectId(user_id)
    target = await db.users.find_one({"_id": target_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user["_id"]) == user_id and not payload.is_active:
        raise HTTPException(status_code=409, detail="You cannot disable your own active admin account.")
    if target.get("role") == "admin" and target.get("is_active", True) and not payload.is_active:
        active_admins = await db.users.count_documents({"role": "admin", "is_active": {"$ne": False}, "account_status": {"$ne": "disabled"}})
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The last active admin cannot be disabled.")
    await db.users.update_one({"_id": target_id}, {"$set": {"is_active": payload.is_active, "account_status": "active" if payload.is_active else "disabled", "updated_at": datetime.now(timezone.utc)}, "$inc": {"auth_version": 1}})
    return {"message": "User status updated", "is_active": payload.is_active}


async def candidate_record(user: dict, db):
    profile = await find_candidate_profile(db, str(user["_id"]))
    completion = profile_completion(profile or {"full_name": user.get("full_name")})
    return {"id": str(user["_id"]), "full_name": user.get("full_name"), "email": user.get("email"), "phone": user.get("contact_number") or (profile or {}).get("phone") or (profile or {}).get("contact_number"), "created_at": user.get("created_at"), "is_active": user.get("is_active", True), "account_status": user.get("account_status", "active"), "profile_completion": completion, "profile": {key: (profile or {}).get(key) for key in ("headline", "location", "summary", "skills", "education", "experience", "projects", "linkedin", "github", "portfolio")}}


@router.get("/candidates")
async def candidates(search: str | None = Query(default=None, max_length=120), status: str | None = None, page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100), _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    import re
    query = {"role": "candidate"}
    if status in {"active", "disabled"}:
        query["is_active"] = status == "active"
    if search and search.strip():
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [{"full_name": {"$regex": pattern}}, {"email": {"$regex": pattern}}]
    values = await paginate(db.users, query, page, limit).to_list(length=limit)
    total = await db.users.count_documents(query)
    return {"items": [await candidate_record(value, db) for value in values], "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/candidates/{candidate_id}")
async def candidate_detail(candidate_id: str, _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")
    user = await db.users.find_one({"_id": ObjectId(candidate_id), "role": "candidate"})
    if not user:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return await candidate_record(user, db)


@router.get("/recruiters")
async def recruiters(search: str | None = Query(default=None, max_length=120), status: str | None = None, page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100), _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    import re
    query = {"role": "recruiter"}
    if status in {"active", "disabled"}:
        query["is_active"] = status == "active"
    if search and search.strip():
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [{"full_name": {"$regex": pattern}}, {"email": {"$regex": pattern}}]
    values = await paginate(db.users, query, page, limit).to_list(length=limit)
    total = await db.users.count_documents(query)
    items = []
    for user in values:
        profile = await db.recruiters.find_one({"user_id": str(user["_id"])})
        company = await db.companies.find_one({"recruiter_id": str(user["_id"])})
        items.append({"id": str(user["_id"]), "full_name": user.get("full_name"), "email": user.get("email"), "phone": user.get("contact_number") or (profile or {}).get("contact_number"), "designation": (profile or {}).get("designation"), "company_id": str(company.get("_id")) if company else None, "company_name": company.get("company_name") if company else None, "created_at": user.get("created_at"), "is_active": user.get("is_active", True), "account_status": user.get("account_status", "active")})
    return {"items": items, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/companies")
async def companies(search: str | None = Query(default=None, max_length=120), page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100), _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    import re
    query = {}
    if search and search.strip():
        query["company_name"] = {"$regex": re.compile(re.escape(search.strip()), re.IGNORECASE)}
    values = await paginate(db.companies, query, page, limit).to_list(length=limit)
    total = await db.companies.count_documents(query)
    items = []
    for company in values:
        recruiter = await db.users.find_one({"_id": ObjectId(company["recruiter_id"])}, {"full_name": 1, "email": 1}) if ObjectId.is_valid(str(company.get("recruiter_id", ""))) else None
        items.append({**serialize(company), "recruiter_name": (recruiter or {}).get("full_name"), "recruiter_email": (recruiter or {}).get("email")})
    return {"items": items, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/companies/{company_id}")
async def company_detail(company_id: str, _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    if not ObjectId.is_valid(company_id):
        raise HTTPException(status_code=400, detail="Invalid company ID")
    company = await db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    recruiter = await db.users.find_one({"_id": ObjectId(company["recruiter_id"])}, {"password_hash": 0}) if ObjectId.is_valid(str(company.get("recruiter_id", ""))) else None
    return {**serialize(company), "recruiter": {"id": str(recruiter["_id"]), "full_name": recruiter.get("full_name"), "email": recruiter.get("email")} if recruiter else None}


@router.get("/jobs")
async def jobs(search: str | None = Query(default=None, max_length=120), status: str | None = None, page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100), _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    import re
    query = {}
    if status in {"draft", "pending", "pending_approval", "published", "paused", "closed", "rejected"}:
        query["status"] = {"$in": ["pending", "pending_approval"]} if status in {"pending", "pending_approval"} else status
    if search and search.strip():
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [{"title": {"$regex": pattern}}, {"company_name": {"$regex": pattern}}, {"location": {"$regex": pattern}}]
    values = await paginate(db.jobs, query, page, limit).to_list(length=limit)
    total = await db.jobs.count_documents(query)
    items = []
    for value in values:
        recruiter = await db.users.find_one({"_id": ObjectId(value["recruiter_id"])}, {"full_name": 1, "email": 1}) if ObjectId.is_valid(str(value.get("recruiter_id", ""))) else None
        value["applicant_count"] = await db.applications.count_documents({"job_id": str(value["_id"])})
        items.append({**serialize(value), "recruiter_name": (recruiter or {}).get("full_name"), "recruiter_email": (recruiter or {}).get("email")})
    return {"items": items, "total": total, "page": page, "pages": (total + limit - 1) // limit}


async def decide_job(job_id: str, status: str, admin: dict, db, reason: str | None = None):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") not in {"pending", "pending_approval"}:
        raise HTTPException(status_code=409, detail="Only jobs pending approval can be approved or rejected.")
    now = datetime.now(timezone.utc)
    decision = {"status": status, "reason": reason, "at": now, "actor_id": str(admin["_id"]), "actor_role": "admin", "actor_name": admin.get("full_name")}
    updated = await db.jobs.update_one({"_id": job["_id"], "status": job["status"]}, {"$set": {"status": status, "is_active": status == "published", "updated_at": now, "rejection_reason": reason if status == "rejected" else None}, "$push": {"approval_history": decision, "status_history": {"previous_status": job["status"], "new_status": status, **decision}}})
    if not updated.modified_count:
        raise HTTPException(status_code=409, detail="This job was updated by another admin. Refresh and review again.")
    if job.get("recruiter_id"):
        await create_notification(db, job["recruiter_id"], f"Job {status}", f"Your job posting {job.get('title', '')} was {status}.{f' Reason: {reason}' if reason else ''}", "job_update", job_id, "/jobs")
    return {"message": f"Job {status}", "status": status}


@router.patch("/jobs/{job_id}/approve")
async def approve_job(job_id: str, admin: dict = Depends(require_role("admin")), db=Depends(get_database)):
    return await decide_job(job_id, "published", admin, db)


@router.patch("/jobs/{job_id}/reject")
async def reject_job(job_id: str, payload: JobRejection, admin: dict = Depends(require_role("admin")), db=Depends(get_database)):
    return await decide_job(job_id, "rejected", admin, db, payload.reason)


@router.put("/jobs/{job_id}/status")
async def legacy_job_status(job_id: str, payload: dict, admin: dict = Depends(require_role("admin")), db=Depends(get_database)):
    if payload.get("status") == "published":
        return await decide_job(job_id, "published", admin, db)
    if payload.get("status") == "rejected":
        reason = str(payload.get("reason", "Rejected by administrator")).strip()
        return await decide_job(job_id, "rejected", admin, db, reason)
    if payload.get("status") not in {"closed", "pending"} or not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=422, detail="Invalid job status or ID")
    result = await db.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": {"status": payload["status"], "is_active": False, "updated_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job status updated"}


@router.get("/applications")
async def applications(search: str | None = Query(default=None, max_length=120), status: str | None = None, page: int = Query(default=1, ge=1), limit: int = Query(default=25, ge=1, le=100), _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    import re
    query = {}
    if status:
        query["status"] = status
    if search and search.strip():
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        users = await db.users.find({"$or": [{"full_name": {"$regex": pattern}}, {"email": {"$regex": pattern}}]}, {"_id": 1}).to_list(length=1000)
        candidate_ids = [str(item["_id"]) for item in users]
        jobs_found = await db.jobs.find({"$or": [{"title": {"$regex": pattern}}, {"company_name": {"$regex": pattern}}]}, {"_id": 1}).to_list(length=1000)
        job_ids = [str(item["_id"]) for item in jobs_found]
        query["$or"] = [{"candidate_id": {"$in": candidate_ids}}, {"job_id": {"$in": job_ids}}]
    values = await paginate(db.applications, query, page, limit).to_list(length=limit)
    total = await db.applications.count_documents(query)
    items = []
    for value in values:
        candidate = await db.users.find_one({"_id": ObjectId(value["candidate_id"])}, {"full_name": 1, "email": 1}) if ObjectId.is_valid(str(value.get("candidate_id", ""))) else None
        job = await db.jobs.find_one({"_id": ObjectId(value["job_id"])}, {"title": 1, "company_name": 1}) if ObjectId.is_valid(str(value.get("job_id", ""))) else None
        analysis = None
        if value.get("resume_analysis_id") and ObjectId.is_valid(value["resume_analysis_id"]):
            analysis = await db.resume_analyses.find_one({"_id": ObjectId(value["resume_analysis_id"]), "candidate_id": value.get("candidate_id"), "job_id": value.get("job_id")}, {"percentage": 1, "_id": 1})
        items.append({"id": str(value.pop("_id")), "candidate_name": (candidate or {}).get("full_name", "Candidate"), "candidate_email": (candidate or {}).get("email"), "job_title": (job or {}).get("title") or (value.get("job_snapshot") or {}).get("title"), "company_name": (job or {}).get("company_name") or (value.get("job_snapshot") or {}).get("company_name"), "status": value.get("status"), "created_at": value.get("created_at"), "ai_match_score": analysis.get("percentage") if analysis else None, "status_history": value.get("status_history", [])})
    return {"items": items, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/applications/{application_id}")
async def application_detail(application_id: str, _: dict = Depends(require_role("admin")), db=Depends(get_database)):
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")
    value = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not value:
        raise HTTPException(status_code=404, detail="Application not found")
    candidate = await db.users.find_one({"_id": ObjectId(value["candidate_id"])}, {"full_name": 1, "email": 1}) if ObjectId.is_valid(str(value.get("candidate_id", ""))) else None
    job = await db.jobs.find_one({"_id": ObjectId(value["job_id"])}, {"title": 1, "company_name": 1}) if ObjectId.is_valid(str(value.get("job_id", ""))) else None
    return {"id": str(value.pop("_id")), "candidate_name": (candidate or {}).get("full_name", "Candidate"), "candidate_email": (candidate or {}).get("email"), "job_title": (job or {}).get("title") or (value.get("job_snapshot") or {}).get("title"), "company_name": (job or {}).get("company_name") or (value.get("job_snapshot") or {}).get("company_name"), "created_at": value.get("created_at"), "status": value.get("status"), "cover_letter": value.get("cover_letter"), "screening_answers": value.get("screening_answers", {}), "status_history": value.get("status_history", []), "ai_match_score_snapshot": value.get("ai_match_score_snapshot")}
