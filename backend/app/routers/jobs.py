from datetime import datetime, timedelta, timezone
import re
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.database import get_database
from app.dependencies import current_user, require_role
from app.schemas.jobs import JobCreate
from app.services.application_eligibility import require_eligible_analysis


router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


class ApplicationCreate(BaseModel):
    resume_id: str | None = None
    resume_analysis_id: str | None = None


def serialize_job(job: dict) -> dict:
    job["id"] = str(job.pop("_id"))
    return job


def active_jobs_query(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {"status": "published", "is_active": {"$ne": False}, "$or": [{"application_deadline": None}, {"application_deadline": {"$gte": now}}]}


def is_active_job(job: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    deadline = job.get("application_deadline")
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError:
            return False
    if deadline and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return job.get("status") == "published" and job.get("is_active", True) is not False and (deadline is None or deadline >= now)


async def attach_company_details(db, jobs: list[dict]) -> list[dict]:
    recruiter_ids = list({job.get("recruiter_id") for job in jobs if job.get("recruiter_id")})
    company_object_ids = [ObjectId(job["company_id"]) for job in jobs if ObjectId.is_valid(str(job.get("company_id", "")))]
    company_query = []
    if recruiter_ids:
        company_query.append({"recruiter_id": {"$in": recruiter_ids}})
    if company_object_ids:
        company_query.append({"_id": {"$in": company_object_ids}})
    companies = await db.companies.find({"$or": company_query}).to_list(length=max(len(recruiter_ids), len(company_object_ids))) if company_query else []
    company_by_recruiter = {company.get("recruiter_id"): company for company in companies}
    company_by_id = {str(company["_id"]): company for company in companies}
    for job in jobs:
        company = company_by_id.get(str(job.get("company_id", ""))) or company_by_recruiter.get(job.get("recruiter_id"), {})
        linked_id = company.get("_id") or job.get("company_id")
        job["company_id"] = str(linked_id) if linked_id else None
        for field, value in (("company_name", company.get("company_name")), ("company_description", company.get("description")), ("website", company.get("website")), ("company_location", company.get("location")), ("company_logo", company.get("logo_url") or company.get("logo")), ("industry", company.get("industry"))):
            if value:
                job[field] = value
    return jobs


def salary_floor(salary: str | None) -> int | None:
    if not salary:
        return None
    match = re.search(r"([\d,]+(?:\.\d+)?)", salary)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    normalized = salary.lower()
    multiplier = 100000 if "lpa" in normalized or "lakh" in normalized else 1000 if "k" in normalized else 1000000 if "million" in normalized or normalized.endswith("m") else 1
    return int(amount * multiplier)


@router.get("")
async def list_jobs(keyword: str | None = Query(default=None, max_length=120), location: str | None = Query(default=None, max_length=120), job_type: str | None = Query(default=None, max_length=40), work_mode: str | None = Query(default=None, max_length=40), skills: str | None = Query(default=None, max_length=300), experience: str | None = Query(default=None, max_length=80), company: str | None = Query(default=None, max_length=120), salary_min: int | None = Query(default=None, ge=0, le=1000000000), posted_days: int | None = Query(default=None, ge=1, le=3650), sort: Literal["newest", "salary", "relevance"] = "newest", page: int = Query(default=1, ge=1), limit: int = Query(default=12, ge=1, le=50), db=Depends(get_database)):
    now = datetime.now(timezone.utc)
    query = active_jobs_query(now)
    conditions = []
    search_term = (keyword or "").strip()
    company_term = (company or "").strip()
    company_recruiters = []
    if search_term or company_term:
        company_pattern = re.compile(re.escape(company_term or search_term), re.IGNORECASE)
        matches = await db.companies.find({"company_name": {"$regex": company_pattern}}, {"recruiter_id": 1}).to_list(length=500)
        company_recruiters = [item["recruiter_id"] for item in matches if item.get("recruiter_id")]
    if search_term:
        search_clauses = [{"$text": {"$search": search_term}}]
        if company_recruiters:
            search_clauses.append({"recruiter_id": {"$in": company_recruiters}})
        conditions.append({"$or": search_clauses})
    if company_term:
        if not company_recruiters:
            query["_id"] = {"$exists": False}
        else:
            conditions.append({"recruiter_id": {"$in": company_recruiters}})
    if location:
        query["location"] = {"$regex": re.escape(location.strip()), "$options": "i"}
    if job_type:
        query["job_type"] = {"$regex": f"^{re.escape(job_type.strip())}$", "$options": "i"}
    if work_mode:
        mode_filter = {"$regex": f"^{re.escape(work_mode.strip())}$", "$options": "i"}
        if work_mode.lower() in {"remote", "hybrid", "on-site", "onsite"}:
            conditions.append({"$or": [{"work_mode": mode_filter}, {"job_type": mode_filter}]})
        else:
            query["work_mode"] = mode_filter
    if skills:
        skill_filters = [re.compile(re.escape(skill.strip()), re.IGNORECASE) for skill in skills.split(",") if skill.strip()]
        if skill_filters:
            query["required_skills"] = {"$all": skill_filters}
    if experience:
        query["experience_range"] = {"$regex": re.escape(experience), "$options": "i"}
    if salary_min is not None:
        query["salary_min"] = {"$gte": salary_min}
    if posted_days:
        query["created_at"] = {"$gte": now - timedelta(days=posted_days)}
    if conditions:
        query["$and"] = conditions
    total = await db.jobs.count_documents(query)
    cursor = db.jobs.find(query)
    if sort == "salary":
        cursor = cursor.sort([("salary_min", -1), ("created_at", -1)])
    elif sort == "relevance" and keyword:
        cursor = cursor.sort([("score", {"$meta": "textScore"}), ("created_at", -1)])
    else:
        cursor = cursor.sort("created_at", -1)
    jobs = await cursor.skip((page - 1) * limit).limit(limit).to_list(length=limit)
    jobs = await attach_company_details(db, jobs)
    return {"items": [serialize_job(job) for job in jobs], "page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_job(payload: JobCreate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    job = payload.model_dump()
    job["salary_min"] = job.get("salary_min") or salary_floor(job.get("salary_range"))
    company = await db.companies.find_one({"recruiter_id": str(user["_id"])})
    if not company or not company.get("company_name"):
        raise HTTPException(status_code=409, detail="Complete your company profile before posting a job.")
    now = datetime.now(timezone.utc)
    job.update({"recruiter_id": str(user["_id"]), "company_id": str(company["_id"]), "company_name": company["company_name"], "status": "draft", "is_active": False, "created_at": now, "updated_at": now})
    result = await db.jobs.insert_one(job)
    job["_id"] = result.inserted_id
    return serialize_job(job)


@router.get("/recently-viewed/me")
async def recently_viewed_jobs(user=Depends(require_role("candidate")), db=Depends(get_database), limit: int = Query(12, ge=1, le=50)):
    views = await db.job_views.find({"candidate_id": str(user["_id"])}).sort("viewed_at", -1).limit(limit).to_list(length=limit)
    ids = [ObjectId(item["job_id"]) for item in views if ObjectId.is_valid(str(item.get("job_id", "")))]
    if not ids:
        return []
    jobs = await db.jobs.find({"_id": {"$in": ids}, **active_jobs_query()}).to_list(length=limit)
    await attach_company_details(db, jobs)
    by_id = {str(job["_id"]): job for job in jobs}
    return [serialize_job(by_id[item["job_id"]]) for item in views if item["job_id"] in by_id]


@router.delete("/recently-viewed/me")
async def clear_recently_viewed(user=Depends(require_role("candidate")), db=Depends(get_database)):
    result = await db.job_views.delete_many({"candidate_id": str(user["_id"])})
    return {"deleted": result.deleted_count}


@router.post("/{job_id}/view", status_code=204)
async def record_job_view(job_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), **active_jobs_query()})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.job_views.update_one({"candidate_id": str(user["_id"]), "job_id": job_id},
        {"$set": {"viewed_at": datetime.now(timezone.utc)}}, upsert=True)


@router.get("/{job_id}")
async def get_job(job_id: str, db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), **active_jobs_query()})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await attach_company_details(db, [job])
    return serialize_job(job)


@router.put("/{job_id}")
async def update_job(job_id: str, payload: JobCreate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    current = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])})
    if not current:
        raise HTTPException(status_code=404, detail="Job not found")
    if current.get("status") in {"closed", "rejected"}:
        raise HTTPException(status_code=409, detail="Closed or rejected jobs cannot be edited.")
    values = {**payload.model_dump(), "updated_at": datetime.now(timezone.utc)}
    company = await db.companies.find_one({"recruiter_id": str(user["_id"])})
    if company:
        values.update({"company_id": str(company["_id"]), "company_name": company.get("company_name")})
    await db.jobs.update_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])}, {"$set": values})
    return await db.jobs.find_one({"_id": ObjectId(job_id)})


@router.delete("/{job_id}")
async def delete_job(job_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "draft":
        raise HTTPException(status_code=409, detail="Only draft jobs can be deleted. Close or pause this job instead.")
    if await db.applications.count_documents({"job_id": job_id}):
        raise HTTPException(status_code=409, detail="This job has applications and cannot be deleted.")
    await db.jobs.delete_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"]), "status": "draft"})
    return {"message": "Job deleted"}


@router.post("/{job_id}/apply", status_code=status.HTTP_201_CREATED)
async def apply_to_job(job_id: str, payload: ApplicationCreate | None = None, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), **active_jobs_query()})
    if not job:
        raise HTTPException(status_code=404, detail="This job is not published or is no longer accepting applications.")
    candidate_id = str(user["_id"])
    if str(job.get("recruiter_id", "")) == candidate_id:
        raise HTTPException(status_code=403, detail="You cannot apply to your own job posting.")
    existing = await db.applications.find_one({"candidate_id": candidate_id, "job_id": job_id})
    if existing:
        raise HTTPException(status_code=409, detail="You have already applied for this job.")
    selected_resume = None
    requested_resume_id = payload.resume_id if payload else None
    if requested_resume_id:
        if not ObjectId.is_valid(requested_resume_id):
            raise HTTPException(status_code=400, detail="Invalid resume ID")
        selected_resume = await db.resumes.find_one({"_id": ObjectId(requested_resume_id), "candidate_id": candidate_id})
        if not selected_resume:
            raise HTTPException(status_code=404, detail="Selected resume not found")
    else:
        raise HTTPException(status_code=422, detail="Select a resume before applying.")
    if selected_resume.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Wait until resume processing is complete before applying.")
    analysis = await require_eligible_analysis(db, candidate_id, job, selected_resume, payload.resume_analysis_id if payload else None)
    now = datetime.now(timezone.utc)
    application = {"candidate_id": candidate_id, "job_id": job_id, "recruiter_id": job.get("recruiter_id"), "resume_id": str(selected_resume["_id"]), "resume_name": selected_resume.get("original_name"), "resume_analysis_id": str(analysis["_id"]), "ai_match_score_snapshot": analysis.get("percentage"), "status": "submitted", "created_at": now, "updated_at": now, "status_history": [{"previous_status": None, "new_status": "submitted", "status": "submitted", "at": now, "actor_id": candidate_id, "actor_role": "candidate"}]}
    try:
        result = await db.applications.insert_one(application)
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="You have already applied for this job.")
        raise
    application["id"] = str(result.inserted_id)
    application.pop("_id", None)
    return application


@router.get("/applications/mine")
async def my_applications(user=Depends(current_user), db=Depends(get_database)):
    applications = await db.applications.find({"candidate_id": str(user["_id"])}).sort("created_at", -1).to_list(length=100)
    for application in applications:
        application["id"] = str(application.pop("_id"))
    return applications


@router.put("/applications/{application_id}/withdraw")
async def withdraw_application(application_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")
    candidate_id = str(user["_id"])
    current = await db.applications.find_one({"_id": ObjectId(application_id), "candidate_id": candidate_id})
    if not current:
        raise HTTPException(status_code=404, detail="Application not found")
    old_status = current.get("status", "submitted")
    if old_status in {"selected", "accepted", "rejected", "withdrawn"}:
        raise HTTPException(status_code=409, detail="This application can no longer be withdrawn.")
    now = datetime.now(timezone.utc)
    result = await db.applications.update_one({"_id": current["_id"], "candidate_id": candidate_id, "status": old_status}, {"$set": {"status": "withdrawn", "updated_at": now}, "$push": {"status_history": {"previous_status": old_status, "new_status": "withdrawn", "status": "withdrawn", "at": now, "actor_id": candidate_id, "actor_role": "candidate"}}})
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="Application status changed. Refresh and try again.")
    return {"message": "Application withdrawn"}


@router.post("/{job_id}/save")
async def save_job(job_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    if not await db.jobs.find_one({"_id": ObjectId(job_id), **active_jobs_query()}):
        raise HTTPException(status_code=404, detail="Published job not found or no longer active")
    try:
        await db.saved_jobs.insert_one({"candidate_id": str(user["_id"]), "job_id": job_id, "created_at": datetime.now(timezone.utc)})
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Job is already saved")
        raise
    return {"message": "Job saved"}


@router.delete("/{job_id}/save")
async def unsave_job(job_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    result = await db.saved_jobs.delete_one({"candidate_id": str(user["_id"]), "job_id": job_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Saved job not found")
    return {"message": "Job removed from saved jobs"}


@router.get("/saved/mine")
@router.get("/saved/me")
async def saved_jobs(user=Depends(require_role("candidate")), db=Depends(get_database)):
    saved = await db.saved_jobs.find({"candidate_id": str(user["_id"])}).sort("created_at", -1).to_list(length=100)
    job_ids = [ObjectId(item["job_id"]) for item in saved if ObjectId.is_valid(item.get("job_id", ""))]
    jobs = await db.jobs.find({"_id": {"$in": job_ids}}).to_list(length=100)
    jobs = await attach_company_details(db, jobs)
    jobs_by_id = {str(job["_id"]): job for job in jobs}
    output = []
    now = datetime.now(timezone.utc)
    for saved_item in saved:
        job_id = saved_item.get("job_id", "")
        job = jobs_by_id.get(job_id) if ObjectId.is_valid(job_id) else None
        if job:
            item = serialize_job(job)
            item["saved_at"] = saved_item.get("created_at")
            item["is_available"] = is_active_job(item, now)
        else:
            item = {"id": job_id, "job_id": job_id, "saved_at": saved_item.get("created_at"), "is_available": False}
        output.append(item)
    return output
