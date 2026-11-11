from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_database
from app.dependencies import require_role
from app.routers.jobs import active_jobs_query, attach_company_details
from app.services.application_eligibility import ATS_MINIMUM_PERCENTAGE, meets_ats_minimum
from app.services.resume_matching import analyze_resume_match
from app.services.resume_matching import analyze_jobs_with_gemini

router = APIRouter(prefix="/api/matching", tags=["Resume Analysis"])
job_match_router = APIRouter(prefix="/api/job-match", tags=["Resume Analysis"])
resume_analysis_router = APIRouter(prefix="/api/resume-analysis", tags=["Resume Analysis"])


class MatchRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=64)
    resume_id: str | None = Field(default=None, max_length=64)


class ResumeSelection(BaseModel):
    resume_id: str | None = Field(default=None, max_length=64)


def serialize_analysis(value: dict) -> dict:
    result = dict(value)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    result["ats_minimum"] = ATS_MINIMUM_PERCENTAGE
    result["meets_ats_minimum"] = meets_ats_minimum(result.get("percentage"))
    return result


async def _analyze(job_id: str, resume_id: str | None, user: dict, db):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), **active_jobs_query()})
    if not job:
        raise HTTPException(status_code=404, detail="Published job not found or no longer active")

    candidate_id = str(user["_id"])
    if resume_id:
        if not ObjectId.is_valid(resume_id):
            raise HTTPException(status_code=400, detail="Invalid resume ID")
        resume = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": candidate_id})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if resume.get("status") != "completed":
            raise HTTPException(status_code=409, detail=f"Resume text extraction is {resume.get('status', 'not complete')}. Wait for processing to finish.")
    else:
        resume = await db.resumes.find_one({"candidate_id": candidate_id, "status": "completed"}, sort=[("processed_at", -1), ("created_at", -1)])
        if not resume:
            any_resume = await db.resumes.find_one({"candidate_id": candidate_id})
            detail = "Wait for resume text extraction to complete before analyzing." if any_resume else "Upload a PDF resume before analyzing this job."
            raise HTTPException(status_code=409 if any_resume else 404, detail=detail)

    resume_version = resume.get("ocr_corrected_at") or resume.get("processed_at")
    job_version = job.get("updated_at") or job.get("created_at")

    try:
        score = analyze_resume_match(resume, job)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await attach_company_details(db, [job])
    now = datetime.now(timezone.utc)
    result = {
        "candidate_id": candidate_id,
        "resume_id": str(resume["_id"]),
        "resume_name": resume.get("original_name"),
        "resume_processed_at": resume.get("processed_at"),
        "resume_version": resume_version,
        "job_id": job_id,
        "job_updated_at": job.get("updated_at") or job.get("created_at"),
        "job_version": job_version,
        "job_snapshot": {key: job.get(key) for key in ("title", "company_name", "location", "job_type", "work_mode", "salary_range")},
        **score,
        "created_at": now,
    }
    inserted = await db.resume_analyses.insert_one(result)
    result["_id"] = inserted.inserted_id
    return serialize_analysis(result)


@resume_analysis_router.post("/analyze/{job_id}")
async def analyze_job(job_id: str, payload: ResumeSelection | None = None, user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await _analyze(job_id, payload.resume_id if payload else None, user, db)


@router.post("/analyze")
async def analyze(payload: MatchRequest, user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await _analyze(payload.job_id, payload.resume_id, user, db)


@job_match_router.post("/{job_id}")
async def analyze_job_alias(job_id: str, resume_id: str | None = Query(default=None), user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await _analyze(job_id, resume_id, user, db)


@resume_analysis_router.get("/me")
async def my_analyses(limit: int = Query(default=50, ge=1, le=100), user=Depends(require_role("candidate")), db=Depends(get_database)):
    values = await db.resume_analyses.find({"candidate_id": str(user["_id"])}).sort("created_at", -1).to_list(length=limit)
    total = await db.resume_analyses.count_documents({"candidate_id": str(user["_id"])})
    return {"items": [serialize_analysis(value) for value in values], "total": total}


@router.get("/history")
async def history(limit: int = Query(default=50, ge=1, le=100), user=Depends(require_role("candidate")), db=Depends(get_database)):
    values = await db.resume_analyses.find({"candidate_id": str(user["_id"])}).sort("created_at", -1).to_list(length=limit)
    return [serialize_analysis(value) for value in values]


@resume_analysis_router.get("/{analysis_id}")
async def get_analysis(analysis_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(analysis_id):
        raise HTTPException(status_code=400, detail="Invalid analysis ID")
    value = await db.resume_analyses.find_one({"_id": ObjectId(analysis_id), "candidate_id": str(user["_id"])})
    if not value:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return serialize_analysis(value)


@resume_analysis_router.delete("/{analysis_id}")
async def delete_analysis(analysis_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(analysis_id):
        raise HTTPException(status_code=400, detail="Invalid analysis ID")
    result = await db.resume_analyses.delete_one({"_id": ObjectId(analysis_id), "candidate_id": str(user["_id"])})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Analysis deleted"}



@router.get("/job-matches")
async def get_ai_job_matches(
    user=Depends(require_role("candidate")),
    db=Depends(get_database)
):
    candidate_id = str(user["_id"])

    resume = await db.resumes.find_one(
        {
            "candidate_id": candidate_id,
            "status": "completed"
        },
        sort=[("processed_at", -1), ("created_at", -1)]
    )

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Please upload a completed resume before matching jobs."
        )

    jobs = await db.jobs.find(
        active_jobs_query()
    ).sort("created_at", -1).to_list(length=10)

    if not jobs:
        return {"items": [], "message": "No published jobs found."}

    try:
        matches = await analyze_jobs_with_gemini(resume, jobs)

    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        ) from exc

    job_map = {
        str(job["_id"]): job for job in jobs
    }

    items = []

    for match in matches:
        job = job_map.get(match["job_id"])

        if not job:
            continue

        await attach_company_details(db, [job])

        items.append({
            "id": match["job_id"],
            "title": job.get("title"),
            "company_name": job.get("company_name"),
            "location": job.get("location"),
            "job_type": job.get("job_type"),
            "work_mode": job.get("work_mode"),
            "experience_range": job.get("experience_range"),
            **match
        })

    items.sort(
        key=lambda item: item["percentage"],
        reverse=True
    )

    return {
        "items": items,
        "resume_id": str(resume["_id"]),
        "total": len(items)
    }
