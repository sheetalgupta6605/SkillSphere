import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from app.database import get_database
from app.database.profiles import profile_completion
from app.dependencies import require_role
from app.routers.resumes import safe_resume_path

router = APIRouter(prefix="/api/recruiter/resume-search", tags=["Recruiter Resume Search"])


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    query: str = Field(default="", max_length=240)
    filters: dict = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value):
        return value.strip()


class CandidateNotes(BaseModel):
    notes: str = Field(default="", max_length=2000)


class CandidateComparison(BaseModel):
    candidate_ids: list[str] = Field(min_length=2, max_length=3)

    @field_validator("candidate_ids")
    @classmethod
    def distinct_ids(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Choose different candidates to compare.")
        return values


def _list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _terms(query: str):
    tokens = re.findall(r'"[^"]+"|\bAND\b|\bOR\b|\bNOT\b|[^\s]+', query, re.IGNORECASE)
    groups, required, excluded = [], [], []
    negate = False
    for token in tokens:
        upper = token.upper()
        if upper == "OR":
            if required or excluded:
                groups.append((required, excluded))
            required, excluded, negate = [], [], False
        elif upper == "AND":
            continue
        elif upper == "NOT":
            negate = True
        else:
            term = token.strip('"').casefold()
            (excluded if negate else required).append(term)
            negate = False
    if required or excluded:
        groups.append((required, excluded))
    return groups


def _matches_query(search_text: str, groups) -> bool:
    if not groups:
        return True
    text = search_text.casefold()
    return any(all(term in text for term in required) and all(term not in text for term in excluded) for required, excluded in groups)


def _years(profile: dict, raw_text: str) -> float | None:
    source = str(profile.get("total_experience") or "")
    match = re.search(r"(\d+(?:\.\d+)?)", source)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", raw_text, re.IGNORECASE)
    return float(match.group(1)) if match else (0.0 if not profile.get("experience") else None)


def _candidate_search_text(profile: dict, resume: dict | None) -> str:
    parts = [profile.get(key, "") for key in ("full_name", "headline", "summary", "current_job_title", "location", "city", "state", "country", "total_experience")]
    parts += _list(profile.get("skills"))
    for key in ("education", "experience", "projects", "certifications"):
        for record in profile.get(key, []) if isinstance(profile.get(key), list) else []:
            if isinstance(record, dict):
                parts.extend(str(value) for value in record.values() if isinstance(value, (str, int, float)))
    extracted = (resume or {}).get("extracted_data") or {}
    parts.extend([str(extracted.get("raw_text") or "")[:30000], " ".join(_list(extracted.get("skills")))])
    return " ".join(str(part) for part in parts if part).casefold()


def _candidate_result(profile: dict, account: dict, resume: dict | None, notes: str | None = None, application_status: str | None = None) -> dict:
    extracted = (resume or {}).get("extracted_data") or {}
    education = profile.get("education") or extracted.get("education") or []
    skills = list(dict.fromkeys(_list(profile.get("skills")) + _list(extracted.get("skills"))))
    years = _years(profile, str(extracted.get("raw_text") or ""))
    return {
        "id": str(account["_id"]), "full_name": profile.get("full_name") or account.get("full_name") or "Candidate",
        "headline": profile.get("headline") or profile.get("current_job_title"), "location": ", ".join(filter(None, [profile.get("city"), profile.get("state"), profile.get("country")])) or profile.get("location"),
        "total_experience": profile.get("total_experience"), "experience_years": years,
        "education": education, "skills": skills[:30], "profile_completion": profile_completion(profile).get("percentage", 0),
        "resume": {"available": bool(resume), "name": resume.get("original_name") if resume else None, "uploaded_at": resume.get("upload_date") or resume.get("created_at") if resume else None},
        "application_status": application_status, "profile_photo": profile.get("profile_photo"), "notes": notes,
    }


async def _discoverable_profiles(db, candidate_ids: list[str] | None = None):
    query = {"recruiter_discoverable": True}
    if candidate_ids is not None:
        query["user_id"] = {"$in": candidate_ids}
    canonical = await db.candidates.find(query).to_list(length=5000)
    legacy = await db.candidate_profiles.find(query).to_list(length=5000)
    by_user = {profile.get("user_id"): profile for profile in [*legacy, *canonical] if profile.get("user_id")}
    return by_user


async def _candidate_data(db, recruiter_id: str, job_id: str | None = None, search_params: dict | None = None):
    profiles = await _discoverable_profiles(db)
    if not profiles:
        return [], 0
    ids = list(profiles)
    accounts = await db.users.find({"_id": {"$in": [ObjectId(value) for value in ids if ObjectId.is_valid(value)]}, "role": "candidate", "is_active": {"$ne": False}, "account_status": {"$ne": "disabled"}}, {"password_hash": 0}).to_list(length=5000)
    accounts_by_id = {str(item["_id"]): item for item in accounts}
    resume_rows = await db.resumes.aggregate([
        {"$match": {"candidate_id": {"$in": ids}, "status": "completed"}},
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$candidate_id", "resume": {"$first": "$$ROOT"}}},
    ]).to_list(length=5000)
    resumes = {item["_id"]: item["resume"] for item in resume_rows}
    saved = await db.saved_candidates.find({"recruiter_id": recruiter_id, "candidate_id": {"$in": ids}}).to_list(length=5000)
    saved_by_id = {item["candidate_id"]: item for item in saved}
    statuses = {}
    if job_id:
        if not ObjectId.is_valid(job_id) or not await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": recruiter_id}):
            raise HTTPException(status_code=404, detail="Job not found in your workspace")
        applications = await db.applications.find({"job_id": job_id, "candidate_id": {"$in": ids}}, {"candidate_id": 1, "status": 1}).to_list(length=5000)
        statuses = {item["candidate_id"]: item.get("status") for item in applications}
    items = []
    params = search_params or {}
    groups = _terms(params.get("query", ""))
    required = [skill.casefold() for skill in _list(params.get("required_skills"))]
    preferred = [skill.casefold() for skill in _list(params.get("preferred_skills"))]
    excluded = [skill.casefold() for skill in _list(params.get("excluded_skills"))]
    for candidate_id, profile in profiles.items():
        account = accounts_by_id.get(candidate_id)
        if not account:
            continue
        resume = resumes.get(candidate_id)
        text = _candidate_search_text(profile, resume)
        skill_text = " ".join(_list(profile.get("skills")) + _list((resume or {}).get("extracted_data", {}).get("skills"))).casefold()
        if not _matches_query(text, groups):
            continue
        if any(skill not in skill_text for skill in required) or any(skill in skill_text for skill in excluded):
            continue
        if preferred and not any(skill in skill_text for skill in preferred):
            continue
        if params.get("location") and str(params["location"]).casefold() not in text:
            continue
        if params.get("education") and str(params["education"]).casefold() not in text:
            continue
        if params.get("designation") and str(params["designation"]).casefold() not in text:
            continue
        if params.get("certification") and str(params["certification"]).casefold() not in text:
            continue
        if params.get("job_type") and str(params["job_type"]).casefold() not in text:
            continue
        if params.get("work_mode") and str(params["work_mode"]).casefold() not in text:
            continue
        years = _years(profile, str((resume or {}).get("extracted_data", {}).get("raw_text") or ""))
        if params.get("min_experience") is not None and (years is None or years < float(params["min_experience"])):
            continue
        if params.get("max_experience") is not None and (years is None or years > float(params["max_experience"])):
            continue
        if params.get("resume_available") is True and not resume:
            continue
        if params.get("resume_available") is False and resume:
            continue
        if params.get("min_completion") is not None and profile_completion(profile).get("percentage", 0) < int(params["min_completion"]):
            continue
        saved_doc = saved_by_id.get(candidate_id)
        result = _candidate_result(profile, account, resume, saved_doc.get("notes") if saved_doc else None, statuses.get(candidate_id))
        result["is_saved"] = bool(saved_doc)
        if params.get("sort") == "experience":
            result["_sort"] = years if years is not None else -1
        elif params.get("sort") == "name":
            result["_sort"] = result["full_name"].casefold()
        else:
            result["_sort"] = sum(1 for term in groups[0][0] if term in text) if groups else len(set(required) & set(skill_text.split()))
        items.append(result)
    sort = params.get("sort", "relevance")
    items.sort(key=lambda item: item["_sort"], reverse=sort != "name")
    for item in items:
        item.pop("_sort", None)
    return items, len(items)


@router.get("")
async def search_candidates(query: str = Query(default="", max_length=240), required_skills: str = "", preferred_skills: str = "", excluded_skills: str = "", min_experience: float | None = Query(default=None, ge=0, le=60), max_experience: float | None = Query(default=None, ge=0, le=60), education: str | None = Query(default=None, max_length=120), location: str | None = Query(default=None, max_length=120), job_type: str | None = Query(default=None, max_length=40), work_mode: str | None = Query(default=None, max_length=40), designation: str | None = Query(default=None, max_length=120), certification: str | None = Query(default=None, max_length=120), resume_available: bool | None = None, min_completion: int | None = Query(default=None, ge=0, le=100), job_id: str | None = None, sort: str = Query(default="relevance", pattern="^(relevance|name|experience)$"), page: int = Query(default=1, ge=1), limit: int = Query(default=20, ge=1, le=50), user=Depends(require_role("recruiter")), db=Depends(get_database)):
    params = {"query": query, "required_skills": required_skills, "preferred_skills": preferred_skills, "excluded_skills": excluded_skills, "min_experience": min_experience, "max_experience": max_experience, "education": education, "location": location, "job_type": job_type, "work_mode": work_mode, "designation": designation, "certification": certification, "resume_available": resume_available, "min_completion": min_completion, "sort": sort}
    items, total = await _candidate_data(db, str(user["_id"]), job_id, params)
    start = (page - 1) * limit
    return {"items": items[start:start + limit], "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/jobs")
async def recruiter_jobs(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    jobs = await db.jobs.find({"recruiter_id": str(user["_id"])}).sort("created_at", -1).to_list(length=200)
    return [{"id": str(job["_id"]), "title": job.get("title"), "status": job.get("status")} for job in jobs]


@router.get("/saved-candidates")
async def saved_candidates(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    saved = await db.saved_candidates.find({"recruiter_id": str(user["_id"])}).sort("updated_at", -1).to_list(length=500)
    profiles = await _discoverable_profiles(db, [item["candidate_id"] for item in saved])
    ids = list(profiles)
    accounts = await db.users.find({"_id": {"$in": [ObjectId(value) for value in ids if ObjectId.is_valid(value)]}, "role": "candidate", "is_active": {"$ne": False}}).to_list(length=500)
    account_map = {str(item["_id"]): item for item in accounts}
    resume_rows = await db.resumes.aggregate([{"$match": {"candidate_id": {"$in": ids}, "status": "completed"}}, {"$sort": {"created_at": -1}}, {"$group": {"_id": "$candidate_id", "resume": {"$first": "$$ROOT"}}}]).to_list(length=500)
    resume_map = {item["_id"]: item["resume"] for item in resume_rows}
    return [{**_candidate_result(profiles[item["candidate_id"]], account_map[item["candidate_id"]], resume_map.get(item["candidate_id"]), item.get("notes", "")), "is_saved": True, "saved_at": item.get("created_at")} for item in saved if item.get("candidate_id") in profiles and item.get("candidate_id") in account_map]


@router.post("/saved-candidates/{candidate_id}", status_code=201)
async def save_candidate(candidate_id: str, payload: CandidateNotes | None = None, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")
    profile = await _discoverable_profiles(db, [candidate_id])
    if candidate_id not in profile or not await db.users.find_one({"_id": ObjectId(candidate_id), "role": "candidate", "is_active": {"$ne": False}}):
        raise HTTPException(status_code=404, detail="Discoverable candidate not found")
    now = datetime.now(timezone.utc)
    await db.saved_candidates.update_one({"recruiter_id": str(user["_id"]), "candidate_id": candidate_id}, {"$set": {"notes": (payload.notes if payload else ""), "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
    return {"saved": True, "candidate_id": candidate_id}


@router.patch("/saved-candidates/{candidate_id}")
async def update_candidate_notes(candidate_id: str, payload: CandidateNotes, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    result = await db.saved_candidates.update_one({"recruiter_id": str(user["_id"]), "candidate_id": candidate_id}, {"$set": {"notes": payload.notes, "updated_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Saved candidate not found")
    return {"saved": True, "candidate_id": candidate_id}


@router.delete("/saved-candidates/{candidate_id}")
async def remove_saved_candidate(candidate_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    result = await db.saved_candidates.delete_one({"recruiter_id": str(user["_id"]), "candidate_id": candidate_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Saved candidate not found")
    return {"saved": False, "candidate_id": candidate_id}


@router.get("/saved-searches")
async def get_saved_searches(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    values = await db.saved_searches.find({"recruiter_id": str(user["_id"])}).sort("updated_at", -1).to_list(length=100)
    return [{**{key: value for key, value in item.items() if key != "recruiter_id"}, "id": str(item.pop("_id"))} for item in values]


@router.post("/saved-searches", status_code=201)
async def create_saved_search(payload: SavedSearchCreate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    now = datetime.now(timezone.utc)
    value = {"recruiter_id": str(user["_id"]), "name": payload.name, "query": payload.query.strip(), "filters": payload.filters, "created_at": now, "updated_at": now}
    try:
        result = await db.saved_searches.insert_one(value)
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A saved search with this name already exists") from exc
        raise
    value["id"] = str(result.inserted_id)
    value.pop("_id", None)
    value.pop("recruiter_id", None)
    return value


@router.put("/saved-searches/{search_id}")
async def edit_saved_search(search_id: str, payload: SavedSearchCreate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(search_id):
        raise HTTPException(status_code=400, detail="Invalid search ID")
    try:
        result = await db.saved_searches.update_one({"_id": ObjectId(search_id), "recruiter_id": str(user["_id"])}, {"$set": {"name": payload.name, "query": payload.query.strip(), "filters": payload.filters, "updated_at": datetime.now(timezone.utc)}})
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A saved search with this name already exists") from exc
        raise
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"id": search_id, "name": payload.name, "query": payload.query.strip(), "filters": payload.filters}


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search(search_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(search_id):
        raise HTTPException(status_code=400, detail="Invalid search ID")
    result = await db.saved_searches.delete_one({"_id": ObjectId(search_id), "recruiter_id": str(user["_id"])})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"deleted": True}


@router.get("/{candidate_id}")
async def candidate_detail(candidate_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")
    profile = await _discoverable_profiles(db, [candidate_id])
    account = await db.users.find_one({"_id": ObjectId(candidate_id), "role": "candidate", "is_active": {"$ne": False}, "account_status": {"$ne": "disabled"}})
    if candidate_id not in profile or not account:
        raise HTTPException(status_code=404, detail="Discoverable candidate not found")
    resume = await db.resumes.find_one({"candidate_id": candidate_id, "status": "completed"}, sort=[("created_at", -1)])
    item = _candidate_result(profile[candidate_id], account, resume)
    for key in ("education", "experience", "projects", "certifications"):
        item[key] = profile[candidate_id].get(key) or ((resume or {}).get("extracted_data") or {}).get(key) or []
    item["summary"] = profile[candidate_id].get("summary") or "Not provided"
    item["linkedin"] = profile[candidate_id].get("linkedin")
    item["github"] = profile[candidate_id].get("github")
    item["portfolio"] = profile[candidate_id].get("portfolio")
    item["current_job_title"] = profile[candidate_id].get("current_job_title") or "Not provided"
    item["headline"] = item.get("headline") or "Not provided"
    return item


@router.get("/{candidate_id}/resume")
async def candidate_resume(candidate_id: str, download: bool = False, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")
    profile = await _discoverable_profiles(db, [candidate_id])
    if candidate_id not in profile or not await db.users.find_one({"_id": ObjectId(candidate_id), "role": "candidate", "is_active": {"$ne": False}}):
        raise HTTPException(status_code=404, detail="Discoverable candidate not found")
    resume = await db.resumes.find_one({"candidate_id": candidate_id, "status": "completed"}, sort=[("created_at", -1)])
    if not resume:
        raise HTTPException(status_code=404, detail="Candidate has no available processed resume")
    path = safe_resume_path(resume.get("stored_name", ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Resume file is unavailable")
    disposition = "attachment" if download else "inline"
    filename = Path(resume.get("original_name") or "resume.pdf").name
    return Response(path.read_bytes(), media_type="application/pdf", headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename, safe='')}", "X-Content-Type-Options": "nosniff"})


@router.post("/compare")
async def compare_candidates(payload: CandidateComparison, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if any(not ObjectId.is_valid(value) for value in payload.candidate_ids):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")
    profiles = await _discoverable_profiles(db, payload.candidate_ids)
    if len(profiles) != len(payload.candidate_ids):
        raise HTTPException(status_code=404, detail="One or more candidates are no longer discoverable")
    accounts = await db.users.find({"_id": {"$in": [ObjectId(value) for value in payload.candidate_ids]}, "role": "candidate", "is_active": {"$ne": False}}).to_list(length=3)
    account_map = {str(item["_id"]): item for item in accounts}
    resume_rows = await db.resumes.aggregate([{"$match": {"candidate_id": {"$in": payload.candidate_ids}, "status": "completed"}}, {"$sort": {"created_at": -1}}, {"$group": {"_id": "$candidate_id", "resume": {"$first": "$$ROOT"}}}]).to_list(length=3)
    resume_map = {item["_id"]: item["resume"] for item in resume_rows}
    return [_candidate_result(profiles[candidate_id], account_map[candidate_id], resume_map.get(candidate_id)) for candidate_id in payload.candidate_ids if candidate_id in account_map]


@router.post("/ai-search")
async def ai_candidate_search(payload: dict, user=Depends(require_role("recruiter"))):
    raise HTTPException(status_code=503, detail="AI resume search is unavailable because no AI provider is configured. Use keyword search and filters instead.")


@router.post("/jobs/{job_id}/matches")
async def match_job_candidates(job_id: str, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    if not ObjectId.is_valid(job_id) or not await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": str(user["_id"])}):
        raise HTTPException(status_code=404, detail="Job not found in your workspace")
    raise HTTPException(status_code=503, detail="AI candidate matching is unavailable because no AI provider is configured. Existing applicants and their saved analyses remain available in Applicants.")
