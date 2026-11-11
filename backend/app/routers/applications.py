from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import get_database
from app.database.profiles import find_candidate_profile
from app.dependencies import require_role
from app.routers.resumes import safe_resume_path
from app.services.application_eligibility import require_eligible_analysis
from app.services.notifications import create_notification
from app.routers.jobs import active_jobs_query, attach_company_details

router = APIRouter(prefix="/api/applications", tags=["Applications"])


class ApplicationCreate(BaseModel):
    resume_id: str | None = Field(default=None, max_length=64)
    cover_letter: str = Field(default="", max_length=10000)
    screening_answers: dict[str, str] = Field(default_factory=dict)
    resume_analysis_id: str | None = Field(default=None, max_length=64)


def serialize(value: dict) -> dict:
    result = dict(value)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    return result


async def hydrate(value: dict, db) -> dict:
    result = serialize(value)
    job_id = result.get("job_id", "")
    job = await db.jobs.find_one({"_id": ObjectId(job_id)}) if ObjectId.is_valid(job_id) else None
    if job:
        await attach_company_details(db, [job])
        result["job_title"] = job.get("title")
        result["company_name"] = job.get("company_name")
        result["company_logo"] = job.get("company_logo") or job.get("logo_url")
        result["job"] = {key: job.get(key) for key in ("title", "description", "location", "job_type", "salary_range", "company_name", "company_logo", "website", "company_description")}
    elif result.get("job_snapshot"):
        result["job"] = result["job_snapshot"]
    resume_id = result.get("resume_id", "")
    resume = await db.resumes.find_one({"_id": ObjectId(resume_id)}) if ObjectId.is_valid(resume_id) else None
    result["resume_name"] = result.get("resume_name") or (resume.get("original_name") if resume else None)
    if result.get("resume_analysis_id") and ObjectId.is_valid(result["resume_analysis_id"]):
        analysis = await db.resume_analyses.find_one({"_id": ObjectId(result["resume_analysis_id"]), "candidate_id": result.get("candidate_id"), "job_id": result.get("job_id")})
        if analysis:
            result["ai_match_score_snapshot"] = analysis.get("percentage")
    return result


async def submit_application(job_id: str, payload: ApplicationCreate, user: dict, db):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), **active_jobs_query()})
    if not job:
        raise HTTPException(status_code=404, detail="This job is not published or is no longer accepting applications.")
    candidate_id = str(user["_id"])
    if str(job.get("recruiter_id", "")) == candidate_id:
        raise HTTPException(status_code=403, detail="You cannot apply to your own job posting.")
    if await db.applications.find_one({"candidate_id": candidate_id, "job_id": job_id}):
        raise HTTPException(status_code=409, detail="You have already applied for this job.")

    # Candidate must have a valid resume to apply
    # First check provided resume_id, then candidate profile resume, then latest completed account resume
    resume = None
    target_resume_id = (payload.resume_id or "").strip()
    if target_resume_id and ObjectId.is_valid(target_resume_id):
        resume = await db.resumes.find_one({"_id": ObjectId(target_resume_id), "candidate_id": candidate_id})

    if not resume:
        profile = await find_candidate_profile(db, candidate_id)
        profile_resume_id = (profile or {}).get("resume_id")
        if profile_resume_id and ObjectId.is_valid(str(profile_resume_id)):
            resume = await db.resumes.find_one({"_id": ObjectId(str(profile_resume_id)), "candidate_id": candidate_id})

    if not resume:
        resume = await db.resumes.find_one({"candidate_id": candidate_id, "status": "completed"}, sort=[("created_at", -1)])

    if not resume:
        raise HTTPException(
            status_code=422,
            detail="A valid resume is mandatory to apply for a job. Please upload a PDF resume before submitting your application."
        )

    if resume.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Wait until resume processing is complete before applying.")

    try:
        file_path = safe_resume_path(resume.get("stored_name", ""))
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="The resume file is unavailable on the server.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail="The resume file is unavailable on the server.") from exc

    resolved_resume_id = str(resume["_id"])
    resolved_resume_name = resume.get("original_name") or "candidate-resume.pdf"

    questions = job.get("screening_questions") or job.get("application_questions") or []
    allowed = {
        str(q.get("id") or q.get("_id") or q.get("question")): q
        for q in questions if isinstance(q, dict)
    }
    allowed.update({question: {"question": question} for question in questions if isinstance(question, str)})
    if set(payload.screening_answers) - set(allowed):
        raise HTTPException(status_code=422, detail="One or more screening answers do not match this job's questions.")
    for key, question in allowed.items():
        required = question.get("required", question.get("is_required", False))
        if required and not str(payload.screening_answers.get(key, "")).strip():
            raise HTTPException(status_code=422, detail=f"Please answer: {question.get('question', key)}")
    if any(len(answer) > 2000 for answer in payload.screening_answers.values()):
        raise HTTPException(status_code=422, detail="Screening answers must be 2,000 characters or fewer.")

    analysis = await require_eligible_analysis(db, candidate_id, job, resume, payload.resume_analysis_id)
    await attach_company_details(db, [job])
    now = datetime.now(timezone.utc)
    application = {
        "candidate_id": candidate_id, "job_id": job_id, "recruiter_id": job.get("recruiter_id"),
        "resume_id": resolved_resume_id, "resume_name": resolved_resume_name,
        "cover_letter": payload.cover_letter.strip(), "screening_answers": payload.screening_answers,
        "resume_analysis_id": str(analysis["_id"]) if analysis else None,
        "ai_match_score_snapshot": analysis.get("percentage") if analysis else None,
        "job_snapshot": {key: job.get(key) for key in ("title", "company_name", "company_logo", "location", "job_type", "salary_range")},
        "status": "submitted", "created_at": now, "updated_at": now,
        "status_history": [{"previous_status": None, "new_status": "submitted", "status": "submitted", "at": now, "actor_id": candidate_id, "actor_role": "candidate"}],
    }
    try:
        inserted = await db.applications.insert_one(application)
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="You have already applied for this job.") from exc
        raise
    application["_id"] = inserted.inserted_id
    app_id = str(inserted.inserted_id)
    await create_notification(db, candidate_id, "Application submitted", f"Your application for {job.get('title', 'this role')} was submitted.", "application_update", app_id, "/applications")
    await create_notification(db, str(job.get("recruiter_id", "")), "New job application", f"A candidate applied for {job.get('title', 'your job') }.", "new_application", app_id, "/applicants")
    return await hydrate(application, db)


@router.post("/{job_id}/apply", status_code=status.HTTP_201_CREATED)
async def apply_for_job(job_id: str, payload: ApplicationCreate, user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await submit_application(job_id, payload, user, db)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(payload: ApplicationCreate, job_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await submit_application(job_id, payload, user, db)


@router.get("/me")
async def list_my_applications(user=Depends(require_role("candidate")), db=Depends(get_database)):
    values = await db.applications.find({"candidate_id": str(user["_id"])}).sort("created_at", -1).to_list(length=200)
    return [await hydrate(value, db) for value in values]


@router.get("/mine")
async def list_my_applications_alias(user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await list_my_applications(user, db)


@router.get("")
async def list_applications(user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await list_my_applications(user, db)


@router.get("/{application_id}")
async def get_application(application_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")
    value = await db.applications.find_one({"_id": ObjectId(application_id), "candidate_id": str(user["_id"])})
    if not value:
        raise HTTPException(status_code=404, detail="Application not found")
    return await hydrate(value, db)


async def withdraw(application_id: str, user: dict, db):
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")
    candidate_id = str(user["_id"])
    current = await db.applications.find_one({"_id": ObjectId(application_id), "candidate_id": candidate_id})
    if not current:
        raise HTTPException(status_code=404, detail="Application not found")
    if current.get("status") in {"accepted", "selected", "rejected", "withdrawn"}:
        raise HTTPException(status_code=409, detail="This application can no longer be withdrawn.")
    now = datetime.now(timezone.utc)
    old = current.get("status", "submitted")
    result = await db.applications.update_one({"_id": current["_id"], "candidate_id": candidate_id, "status": old}, {"$set": {"status": "withdrawn", "updated_at": now}, "$push": {"status_history": {"previous_status": old, "new_status": "withdrawn", "status": "withdrawn", "at": now, "actor_id": candidate_id, "actor_role": "candidate"}}})
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="Application status changed. Refresh and try again.")
    await create_notification(db, str(current.get("recruiter_id", "")), "Candidate withdrew application", "A candidate withdrew their application.", "application_withdrawn", application_id, "/applicants")
    updated = await db.applications.find_one({"_id": current["_id"]})
    return await hydrate(updated, db)


@router.post("/{application_id}/withdraw")
async def withdraw_application_post(application_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await withdraw(application_id, user, db)


@router.put("/{application_id}/withdraw")
async def withdraw_application(application_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await withdraw(application_id, user, db)
