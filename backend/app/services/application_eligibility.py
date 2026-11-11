from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException

ATS_MINIMUM_PERCENTAGE = 70


def meets_ats_minimum(percentage) -> bool:
    return isinstance(percentage, (int, float)) and not isinstance(percentage, bool) and percentage >= ATS_MINIMUM_PERCENTAGE


def _as_timestamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return round(value.timestamp(), 3)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return round(parsed.timestamp(), 3)
    return value


def versions_match(left, right) -> bool:
    return _as_timestamp(left) == _as_timestamp(right)


def analysis_is_current(analysis: dict, resume: dict, job: dict) -> bool:
    resume_id = str(resume.get("_id", resume.get("id", "")))
    job_id = str(job.get("_id", job.get("id", "")))
    if str(analysis.get("resume_id", "")) != resume_id or str(analysis.get("job_id", "")) != job_id:
        return False
    resume_version = resume.get("ocr_corrected_at") or resume.get("processed_at")
    job_version = job.get("updated_at") or job.get("created_at")
    if resume_version is None or job_version is None:
        return False
    return versions_match(analysis.get("resume_version"), resume_version) and versions_match(analysis.get("job_version"), job_version)


async def require_eligible_analysis(db, candidate_id: str, job: dict, resume: dict, analysis_id: str | None) -> dict:
    minimum = ATS_MINIMUM_PERCENTAGE
    analysis = None
    if analysis_id and ObjectId.is_valid(analysis_id):
        analysis = await db.resume_analyses.find_one({
            "_id": ObjectId(analysis_id),
            "candidate_id": candidate_id,
            "job_id": str(job["_id"]),
            "resume_id": str(resume["_id"]),
        })
    if not analysis:
        # Fallback to the latest analysis for this candidate, job, and resume
        analysis = await db.resume_analyses.find_one(
            {
                "candidate_id": candidate_id,
                "job_id": str(job["_id"]),
                "resume_id": str(resume["_id"]),
            },
            sort=[("created_at", -1)],
        )
    if not analysis or not analysis_is_current(analysis, resume, job):
        raise HTTPException(status_code=422, detail=f"Analyze your resume against this job before applying. An ATS score of {minimum}% or higher is required.")
    if not meets_ats_minimum(analysis.get("percentage")):
        score = analysis.get("percentage")
        shown = "not scored" if score is None else f"{score}%"
        raise HTTPException(status_code=422, detail=f"This resume is not applicable. ATS score is {shown}; {minimum}% is required to apply.")
    return analysis
