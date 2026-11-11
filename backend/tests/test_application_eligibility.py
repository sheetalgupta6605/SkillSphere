from datetime import datetime, timezone

import asyncio

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.services.application_eligibility import analysis_is_current, meets_ats_minimum, require_eligible_analysis


def test_ats_minimum_is_75_percent():
    assert meets_ats_minimum(75) is True
    assert meets_ats_minimum(75.0) is True
    assert meets_ats_minimum(74.9) is False
    assert meets_ats_minimum(None) is False
    assert meets_ats_minimum(True) is False


def test_analysis_is_current_only_for_the_same_resume_and_job_versions():
    stamp = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
    resume = {"_id": ObjectId(), "processed_at": stamp}
    job = {"_id": ObjectId(), "updated_at": stamp}
    analysis = {"resume_id": str(resume["_id"]), "job_id": str(job["_id"]), "resume_version": stamp, "job_version": stamp}
    assert analysis_is_current(analysis, resume, job) is True

    changed_resume = {**resume, "ocr_corrected_at": datetime(2026, 11, 11, 7, 0, tzinfo=timezone.utc)}
    assert analysis_is_current(analysis, changed_resume, job) is False

    changed_job = {**job, "updated_at": datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)}
    assert analysis_is_current(analysis, resume, changed_job) is False


class _Analyses:
    def __init__(self, document):
        self.document = document

    async def find_one(self, query):
        if not self.document:
            return None
        if self.document["_id"] != query["_id"]:
            return None
        if self.document["candidate_id"] != query["candidate_id"]:
            return None
        return self.document


class _Database:
    def __init__(self, document):
        self.resume_analyses = _Analyses(document)


def test_apply_requires_a_current_analysis_at_or_above_75():
    stamp = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
    resume = {"_id": ObjectId(), "processed_at": stamp}
    job = {"_id": ObjectId(), "updated_at": stamp}
    analysis_id = ObjectId()
    low = {
        "_id": analysis_id,
        "candidate_id": "candidate",
        "resume_id": str(resume["_id"]),
        "job_id": str(job["_id"]),
        "resume_version": stamp,
        "job_version": stamp,
        "percentage": 74,
    }
    with pytest.raises(HTTPException) as missing:
        asyncio.run(require_eligible_analysis(_Database(low), "candidate", job, resume, None))
    assert missing.value.status_code == 422

    with pytest.raises(HTTPException) as below:
        asyncio.run(require_eligible_analysis(_Database(low), "candidate", job, resume, str(analysis_id)))
    assert "74%" in below.value.detail

    passing = {**low, "percentage": 75}
    allowed = asyncio.run(require_eligible_analysis(_Database(passing), "candidate", job, resume, str(analysis_id)))
    assert allowed["percentage"] == 75

    stale_resume = {**resume, "processed_at": datetime(2026, 11, 12, tzinfo=timezone.utc)}
    with pytest.raises(HTTPException) as stale:
        asyncio.run(require_eligible_analysis(_Database(passing), "candidate", job, stale_resume, str(analysis_id)))
    assert "current job requirements" in stale.value.detail
