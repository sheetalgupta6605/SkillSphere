from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.database import get_database
from app.dependencies import require_role
from app.services.notifications import create_notification
from app.schemas.jobs import JobCreate
from app.routers.jobs import is_active_job, salary_floor
from app.schemas.recruiter import RecruiterProfileUpdate
from app.database.profiles import find_candidate_profile
from app.routers.resumes import safe_resume_path


router = APIRouter(prefix="/api/recruiter", tags=["Recruiter"])


class ApplicationStatusUpdate(BaseModel):
    status: Literal["under_review", "shortlisted", "interview_scheduled", "rejected", "accepted"]


class InterviewSchedule(BaseModel):
    scheduled_at: datetime
    interview_type: Literal["online", "in_person"]
    meeting_link: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=300)
    instructions: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_interview(self):
        scheduled = self.scheduled_at if self.scheduled_at.tzinfo else self.scheduled_at.replace(tzinfo=timezone.utc)
        if scheduled <= datetime.now(timezone.utc):
            raise ValueError("Interview date and time must be in the future")
        if self.interview_type == "online" and not (self.meeting_link or "").startswith(("https://", "http://")):
            raise ValueError("Enter a valid online meeting link")
        if self.interview_type == "in_person" and not (self.location or "").strip():
            raise ValueError("Enter the interview location")
        return self


def serialize_company(company: dict | None):
    if not company:
        return company
    result = dict(company)
    result["id"] = str(result.pop("_id"))
    return result


@router.get("/dashboard")
async def dashboard(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    recruiter_id = str(user["_id"])
    job_docs = await db.jobs.find({"recruiter_id": recruiter_id}).sort("created_at", -1).to_list(length=500)
    job_ids = [str(job["_id"]) for job in job_docs]
    application_query = {"job_id": {"$in": job_ids}}
    total_jobs = len(job_docs)
    active_jobs = sum(1 for job in job_docs if is_active_job(job))
    total_applications = await db.applications.count_documents(application_query) if job_ids else 0
    shortlisted = await db.applications.count_documents({**application_query, "status": "shortlisted"}) if job_ids else 0
    interviews = await db.applications.count_documents({**application_query, "status": {"$in": ["interview", "interview_scheduled"]}}) if job_ids else 0
    rejected = await db.applications.count_documents({**application_query, "status": "rejected"}) if job_ids else 0
    recent = await db.applications.find(application_query).sort("created_at", -1).to_list(length=8) if job_ids else []
    job_by_id = {str(job["_id"]): job for job in job_docs}
    user_ids = [ObjectId(item["candidate_id"]) for item in recent if ObjectId.is_valid(str(item.get("candidate_id", "")))]
    candidate_docs = await db.users.find({"_id": {"$in": user_ids}}, {"_id": 1, "full_name": 1}).to_list(length=len(user_ids)) if user_ids else []
    candidate_names = {str(item["_id"]): item.get("full_name", "Candidate") for item in candidate_docs}
    recent_applications = []
    recent_activity = []
    for item in recent:
        job = job_by_id.get(item.get("job_id"), {})
        app_id = str(item.get("_id", ""))
        candidate_id = item.get("candidate_id", "")
        recent_applications.append({"id": app_id, "candidate_id": candidate_id, "candidate_name": candidate_names.get(candidate_id, "Candidate"), "job_id": item.get("job_id"), "job_title": job.get("title", "Job posting"), "status": item.get("status", "submitted"), "created_at": item.get("created_at"), "resume_name": item.get("resume_name")})
        for event in item.get("status_history", []):
            recent_activity.append({"application_id": app_id, "candidate_name": candidate_names.get(candidate_id, "Candidate"), "job_title": job.get("title", "Job posting"), "status": event.get("new_status") or event.get("status", item.get("status")), "at": event.get("at") or event.get("created_at") or item.get("created_at")})
    recent_activity.sort(key=lambda event: event.get("at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    for job in job_docs[:8]:
        job["id"] = str(job.pop("_id"))
    return {"total_jobs": total_jobs, "active_jobs": active_jobs, "total_applications": total_applications, "total_applicants": total_applications, "shortlisted_candidates": shortlisted, "interviews_scheduled": interviews, "rejected_applications": rejected, "recent_jobs": job_docs[:8], "recent_applications": recent_applications, "recent_activity": recent_activity[:10]}


@router.get("/profile")
async def recruiter_profile(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    user_id = str(user["_id"])
    profile = await db.recruiters.find_one({"user_id": user_id}) or await db.recruiter_profiles.find_one({"user_id": user_id}) or {}
    company = await db.companies.find_one({"recruiter_id": user_id})
    return {"full_name": user.get("full_name", ""), "email": user.get("email", ""), "phone": user.get("contact_number") or profile.get("contact_number") or "", "designation": profile.get("designation", ""), "company_name": company.get("company_name") if company else "", "company_id": profile.get("company_id"), "profile_picture": profile.get("profile_picture")}


@router.put("/profile")
async def update_recruiter_profile(payload: RecruiterProfileUpdate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    user_id = str(user["_id"])
    values = payload.model_dump(exclude_unset=True)
    now = datetime.now(timezone.utc)
    if "full_name" in values:
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"full_name": values["full_name"], "updated_at": now}})
        await db.recruiter_profiles.update_one({"user_id": user_id}, {"$set": {"full_name": values["full_name"], "updated_at": now}})
    if "phone" in values:
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"contact_number": values["phone"], "updated_at": now}})
        await db.recruiters.update_one({"user_id": user_id}, {"$set": {"contact_number": values["phone"], "updated_at": now}})
        await db.recruiter_profiles.update_one({"user_id": user_id}, {"$set": {"contact_number": values["phone"], "updated_at": now}})
    if "designation" in values:
        await db.recruiters.update_one({"user_id": user_id}, {"$set": {"designation": values["designation"], "updated_at": now}})
        await db.recruiter_profiles.update_one({"user_id": user_id}, {"$set": {"designation": values["designation"], "updated_at": now}})
    return await recruiter_profile(user, db)


@router.get("/analytics")
async def analytics(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    recruiter_id = str(user["_id"])
    jobs = await db.jobs.find({"recruiter_id": recruiter_id}, {"_id": 1}).to_list(length=500)
    job_ids = [str(job["_id"]) for job in jobs]
    by_status = {}
    for status in ["applied", "under_review", "shortlisted", "interview", "selected", "rejected"]:
        by_status[status] = await db.applications.count_documents({"job_id": {"$in": job_ids}, "status": status})
    return {"jobs": len(job_ids), "applications_by_status": by_status}


@router.get("/jobs")
async def recruiter_jobs(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    recruiter_id = str(user["_id"])
    jobs = await db.jobs.find({"recruiter_id": recruiter_id}).sort("created_at", -1).to_list(length=200)
    for job in jobs:
        job_id = str(job.pop("_id"))
        job["id"] = job_id
        job["applicant_count"] = await db.applications.count_documents({"job_id": job_id})
        job["is_active"] = is_active_job(job)
    return jobs


@router.post("/jobs", status_code=201)
async def create_recruiter_job(payload: JobCreate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    recruiter_id = str(user["_id"])
    company = await db.companies.find_one({"recruiter_id": recruiter_id})
    if not company or not company.get("company_name"):
        raise HTTPException(status_code=409, detail="Complete your company profile before posting a job.")
    now = datetime.now(timezone.utc)
    job = payload.model_dump()
    job.update({"salary_min": payload.salary_min or salary_floor(payload.salary_range), "recruiter_id": recruiter_id, "company_id": str(company["_id"]), "company_name": company["company_name"], "status": "draft", "is_active": False, "created_at": now, "updated_at": now})
    inserted = await db.jobs.insert_one(job)
    job["id"] = str(inserted.inserted_id)
    job.pop("_id", None)
    job["applicant_count"] = 0
    return job


@router.get("/jobs/{job_id}")
async def recruiter_job_detail(job_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["id"] = str(job.pop("_id"))
    job["applicant_count"] = await db.applications.count_documents({"job_id": job_id})
    return job


@router.put("/jobs/{job_id}")
async def update_recruiter_job(job_id: str, payload: JobCreate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    existing = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])})
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.get("status") in {"closed", "rejected"}:
        raise HTTPException(status_code=409, detail="Closed or rejected jobs cannot be edited.")
    company = await db.companies.find_one({"recruiter_id": str(user["_id"])})
    values = payload.model_dump()
    values["salary_min"] = payload.salary_min or salary_floor(payload.salary_range)
    if company:
        values.update({"company_id": str(company["_id"]), "company_name": company.get("company_name")})
    values["updated_at"] = datetime.now(timezone.utc)
    await db.jobs.update_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])}, {"$set": values})
    result = await db.jobs.find_one({"_id": ObjectId(job_id)})
    result["id"] = str(result.pop("_id"))
    result["applicant_count"] = await db.applications.count_documents({"job_id": job_id})
    return result


@router.patch("/jobs/{job_id}/status")
async def update_recruiter_job_status(job_id: str, payload: dict, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    new_status = payload.get("status")
    if new_status not in {"pending", "published", "paused", "closed"}:
        raise HTTPException(status_code=422, detail="Status must be pending, published, paused, or closed.")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    old_status = job.get("status", "draft")
    if old_status in {"pending", "pending_approval", "rejected"} and new_status == "published":
        raise HTTPException(status_code=403, detail="This job must be approved before it can be published.")
    if new_status == "pending" and old_status != "draft":
        raise HTTPException(status_code=409, detail="Only draft jobs can be submitted for approval.")
    if new_status == "published" and old_status == "draft":
        raise HTTPException(status_code=403, detail="Submit this draft for admin approval before publishing.")
    if old_status == "closed" and new_status != "closed":
        raise HTTPException(status_code=409, detail="Closed jobs cannot be reopened.")
    if new_status == "published" and job.get("application_deadline") and not is_active_job({**job, "status": "published", "is_active": True}):
        raise HTTPException(status_code=422, detail="Set a future application deadline before publishing this job.")
    now = datetime.now(timezone.utc)
    await db.jobs.update_one({"_id": job["_id"], "recruiter_id": str(user["_id"])}, {"$set": {"status": new_status, "is_active": new_status == "published", "updated_at": now}, "$push": {"status_history": {"previous_status": old_status, "new_status": new_status, "at": now, "actor_id": str(user["_id"]), "actor_role": "recruiter", "actor_name": user.get("full_name")}}})
    if new_status == "pending":
        admins = await db.users.find({"role": "admin", "is_active": {"$ne": False}}).to_list(length=100)
        for admin in admins:
            await create_notification(db, str(admin["_id"]), "Job awaiting approval", f"{user.get('full_name', 'A recruiter')} submitted {job.get('title', 'a job')} for review.", "job_pending_approval", job_id, "/admin-jobs")
    return {"id": job_id, "status": new_status, "is_active": new_status == "published"}


@router.delete("/jobs/{job_id}")
async def delete_recruiter_job(job_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "draft":
        raise HTTPException(status_code=409, detail="Only draft jobs can be deleted.")
    if await db.applications.count_documents({"job_id": job_id}):
        raise HTTPException(status_code=409, detail="Jobs with applications cannot be deleted.")
    await db.jobs.delete_one({"_id": job["_id"], "recruiter_id": str(user["_id"]), "status": "draft"})
    return {"message": "Draft job deleted"}


@router.get("/company")
async def get_company(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    company = await db.companies.find_one({"recruiter_id": str(user["_id"])})
    return serialize_company(company) or {"recruiter_id": str(user["_id"])}


@router.put("/company")
async def update_company(data: dict, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    data = {key: value for key, value in data.items() if key not in {"_id", "recruiter_id", "company_id"}}
    data["recruiter_id"] = str(user["_id"])
    await db.companies.update_one({"recruiter_id": str(user["_id"])}, {"$set": data}, upsert=True)
    return serialize_company(await db.companies.find_one({"recruiter_id": str(user["_id"])}))


@router.get("/applicants")
async def applicants(status_filter: str | None = Query(default=None, alias="status"), user=Depends(require_role("recruiter")), db=Depends(get_database)):
    job_docs = await db.jobs.find({"recruiter_id": str(user["_id"])}, {"_id": 1, "title": 1}).to_list(length=500)
    job_ids = [str(job["_id"]) for job in job_docs]
    if not job_ids:
        return []
    query = {"job_id": {"$in": job_ids}}
    if status_filter:
        query["status"] = status_filter
    values = await db.applications.find(query).sort("created_at", -1).to_list(length=500)
    return [await serialize_applicant(value, db, job_docs) for value in values]


async def serialize_applicant(application: dict, db, job_docs: list[dict] | None = None):
    result = dict(application)
    result["id"] = str(result.pop("_id"))
    candidate_id = str(result.get("candidate_id", ""))
    candidate_oid = ObjectId(candidate_id) if ObjectId.is_valid(candidate_id) else None
    candidate_user = await db.users.find_one({"_id": candidate_oid}) if candidate_oid else None
    profile = await find_candidate_profile(db, candidate_id)
    job_id = result.get("job_id", "")
    job = next((item for item in (job_docs or []) if str(item["_id"]) == job_id), None)
    if not job and ObjectId.is_valid(job_id):
        job = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": result.get("recruiter_id")})
    result["job_title"] = (job or {}).get("title") or (result.get("job_snapshot") or {}).get("title")
    result["candidate"] = {
        "id": candidate_id,
        "full_name": (candidate_user or {}).get("full_name") or (profile or {}).get("full_name") or "Candidate",
        "email": (candidate_user or {}).get("email"),
        "phone": (candidate_user or {}).get("contact_number") or (profile or {}).get("phone") or (profile or {}).get("contact_number"),
        "skills": (profile or {}).get("skills", []),
        "education": (profile or {}).get("education", []),
        "experience": (profile or {}).get("experience", []),
        "headline": (profile or {}).get("headline"),
        "summary": (profile or {}).get("summary"),
        "linkedin": (profile or {}).get("linkedin"),
        "portfolio": (profile or {}).get("portfolio"),
    }
    resume_id = result.get("resume_id", "")
    resume = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": candidate_id}) if ObjectId.is_valid(resume_id) else None
    result["resume"] = {"id": resume_id, "name": resume.get("original_name"), "available": bool(resume and safe_resume_path(resume.get("stored_name", "")).is_file()), "status": resume.get("status")} if resume else {"id": resume_id, "name": result.get("resume_name"), "available": False, "status": "unavailable"}
    analysis = None
    analysis_id = result.get("resume_analysis_id")
    if analysis_id and ObjectId.is_valid(analysis_id):
        analysis = await db.resume_analyses.find_one({"_id": ObjectId(analysis_id), "candidate_id": candidate_id, "job_id": job_id, "resume_id": resume_id})
    elif resume_id:
        analysis = await db.resume_analyses.find_one({"candidate_id": candidate_id, "job_id": job_id, "resume_id": resume_id}, sort=[("created_at", -1)])
    if analysis:
        analysis["id"] = str(analysis.pop("_id"))
        result["analysis"] = analysis
    else:
        result["analysis"] = None
    return result


async def owned_application(application_id: str, user: dict, db):
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")
    recruiter_id = str(user["_id"])
    jobs = await db.jobs.find({"recruiter_id": recruiter_id}, {"_id": 1}).to_list(length=500)
    owned_job_ids = {str(job["_id"]) for job in jobs}
    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application or application.get("job_id") not in owned_job_ids:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.get("/applicants/{application_id}")
async def applicant_detail(application_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    application = await owned_application(application_id, user, db)
    return await serialize_applicant(application, db)


@router.get("/analyses/{analysis_id}")
async def recruiter_analysis_detail(analysis_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(analysis_id):
        raise HTTPException(status_code=400, detail="Invalid analysis ID")
    analysis = await db.resume_analyses.find_one({"_id": ObjectId(analysis_id)})
    if not analysis:
        raise HTTPException(status_code=404, detail="Saved analysis not found")
    job = await db.jobs.find_one({"_id": ObjectId(analysis["job_id"]), "recruiter_id": str(user["_id"])}) if ObjectId.is_valid(str(analysis.get("job_id", ""))) else None
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")
    application = await db.applications.find_one({"job_id": analysis["job_id"], "candidate_id": analysis["candidate_id"], "resume_id": analysis["resume_id"]})
    if not application:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis["id"] = str(analysis.pop("_id"))
    analysis["job_title"] = job.get("title")
    return analysis


@router.get("/applicants/{application_id}/resume")
async def applicant_resume(application_id: str, preview: bool = False, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    application = await owned_application(application_id, user, db)
    resume_id = application.get("resume_id", "")
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=404, detail="Candidate did not submit a resume")
    resume = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": application.get("candidate_id")})
    if not resume:
        raise HTTPException(status_code=404, detail="Submitted resume is unavailable")
    path = safe_resume_path(resume.get("stored_name", ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Resume file is unavailable")
    disposition = "inline" if preview else "attachment"
    download_filename = resume.get("original_name") or "candidate-resume.pdf"
    return FileResponse(path, filename=download_filename, media_type="application/pdf", headers={"Content-Disposition": f'{disposition}; filename="{download_filename}"'})


@router.put("/applications/{application_id}/status")
@router.patch("/applicants/{application_id}/status")
async def update_application_status(application_id: str, payload: ApplicationStatusUpdate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    application = await owned_application(application_id, user, db)
    old_status = application.get("status", "submitted")
    if old_status == "withdrawn":
        raise HTTPException(status_code=409, detail="Withdrawn applications cannot be changed.")
    now = datetime.now(timezone.utc)
    new_status = payload.status
    if new_status != old_status:
        update_doc = {"status": new_status, "updated_at": now}
        push_doc = {
            "status_history": {
                "previous_status": old_status,
                "new_status": new_status,
                "status": new_status,
                "at": now,
                "actor_id": str(user["_id"]),
                "actor_role": "recruiter",
                "actor_name": user.get("full_name")
            }
        }
        # If an application becomes Rejected after an interview is scheduled,
        # prevent further scheduling and cancel the existing interview
        existing_interview = application.get("interview")
        interview_cancelled = False
        if new_status == "rejected" and existing_interview and existing_interview.get("status") != "cancelled":
            update_doc["interview.status"] = "cancelled"
            update_doc["interview.cancelled_at"] = now.isoformat()
            update_doc["interview.cancellation_reason"] = "Application rejected"
            push_doc["status_history"]["interview_cancelled"] = True
            interview_cancelled = True

        result = await db.applications.update_one(
            {"_id": application["_id"], "status": old_status},
            {"$set": update_doc, "$push": push_doc}
        )
        if not result.modified_count:
            raise HTTPException(status_code=409, detail="Application status changed. Refresh and try again.")

        job = await db.jobs.find_one({"_id": ObjectId(application["job_id"])}) if ObjectId.is_valid(application.get("job_id", "")) else None
        job_title = job.get('title', 'a role') if job else 'a role'
        await create_notification(db, application["candidate_id"], "Application status updated", f"Your application for {job_title} is now {new_status.replace('_', ' ')}.", "application_update", application_id, "/applications")
        if interview_cancelled:
            await create_notification(db, application["candidate_id"], "Interview cancelled", f"Your scheduled interview for {job_title} was cancelled because the application was rejected.", "interview_cancelled", application_id, "/applications")

    return {"message": "Application status updated", "status": new_status}


@router.post("/applicants/{application_id}/interview", status_code=201)
async def schedule_interview(application_id: str, payload: InterviewSchedule, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    application = await owned_application(application_id, user, db)
    current_status = application.get("status", "submitted")
    if current_status == "rejected":
        raise HTTPException(status_code=400, detail="Cannot schedule an interview for a rejected application.")
    ELIGIBLE_INTERVIEW_STATUSES = {"under_review", "shortlisted", "interview_scheduled"}
    if current_status not in ELIGIBLE_INTERVIEW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Interviews can only be scheduled for applications that are Under Review or Shortlisted (current status: {current_status.replace('_', ' ')})."
        )
    interview = payload.model_dump(mode="json")
    now = datetime.now(timezone.utc)
    interview.update({
        "status": "scheduled",
        "scheduled_by": str(user["_id"]),
        "scheduled_at_timestamp": now.isoformat(),
        "updated_at": now.isoformat()
    })
    old_status = current_status
    updates = {"interview": interview, "updated_at": now}
    update = {"$set": updates}
    if old_status != "interview_scheduled":
        updates["status"] = "interview_scheduled"
        update["$push"] = {"status_history": {"previous_status": old_status, "new_status": "interview_scheduled", "status": "interview_scheduled", "at": now, "actor_id": str(user["_id"]), "actor_role": "recruiter", "actor_name": user.get("full_name")}}
    await db.applications.update_one({"_id": application["_id"]}, update)
    await create_notification(db, application["candidate_id"], "Interview scheduled", "An interview has been scheduled for your application.", "interview_scheduled", application_id, "/applications")
    return {"interview": interview, "status": "interview_scheduled"}


@router.get("/applicants/{application_id}/interview")
async def get_interview(application_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    application = await owned_application(application_id, user, db)
    if not application.get("interview"):
        raise HTTPException(status_code=404, detail="No interview is scheduled for this application.")
    return application["interview"]


