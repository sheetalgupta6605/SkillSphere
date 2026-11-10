import pytest
from pydantic import ValidationError

from app.routers.recruiter import InterviewSchedule
from app.schemas.recruiter import CompanyProfileUpdate, RecruiterProfileUpdate
from app.schemas.jobs import JobCreate
from datetime import datetime, timedelta, timezone
from app.routers.admin import JobRejection, UserStatusUpdate


def test_company_profile_validates_and_ignores_ownership_fields():
    payload = CompanyProfileUpdate(company_name="Acme", recruiter_id="someone-else", company_id="foreign", social_links={"linkedin": "https://linkedin.com/company/acme"})
    assert payload.model_dump(exclude_unset=True) == {"company_name": "Acme", "social_links": {"linkedin": "https://linkedin.com/company/acme"}}


@pytest.mark.parametrize("payload", [
    {"company_email": "not-an-email"},
    {"contact_number": "123"},
    {"social_links": {"linkedin": "javascript:alert(1)"}},
    {"founded_year": 1700},
])
def test_company_profile_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        CompanyProfileUpdate(**payload)


def test_recruiter_profile_cannot_change_role_or_linked_company():
    payload = RecruiterProfileUpdate(full_name="Recruiter Name", role="admin", company_id="foreign")
    assert payload.model_dump(exclude_unset=True) == {"full_name": "Recruiter Name"}


def test_job_posting_validates_fields_and_ignores_client_ownership():
    payload = JobCreate(title="Engineer", description="Build and maintain software for our product team.", location="Remote", recruiter_id="foreign", status="published", required_skills=[" Python ", "Python"])
    assert payload.required_skills == ["Python"]
    assert "recruiter_id" not in payload.model_dump()
    assert "status" not in payload.model_dump()


def test_interview_requires_a_future_date_and_online_link():
    future = datetime.now(timezone.utc) + timedelta(days=2)
    scheduled = InterviewSchedule(scheduled_at=future, interview_type="online", meeting_link="https://meet.example.com/room")
    assert scheduled.interview_type == "online"
    with pytest.raises(ValidationError):
        InterviewSchedule(scheduled_at=future, interview_type="online")
    with pytest.raises(ValidationError):
        InterviewSchedule(scheduled_at=datetime.now(timezone.utc) - timedelta(days=1), interview_type="in_person", location="Office")


def test_admin_decision_schemas_validate_job_rejection_and_account_state():
    assert JobRejection(reason="  Missing salary range  ").reason == "Missing salary range"
    assert UserStatusUpdate(is_active=False).is_active is False
    with pytest.raises(ValidationError):
        JobRejection(reason="  ")
