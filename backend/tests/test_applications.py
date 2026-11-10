import pytest
from pydantic import ValidationError

from app.routers.applications import ApplicationCreate


def test_application_payload_accepts_resume_cover_letter_and_answers():
    payload = ApplicationCreate(resume_id="64a123456789abcdef123456", cover_letter="Hello", screening_answers={"q1": "Yes"})
    assert payload.resume_id == "64a123456789abcdef123456"
    assert payload.screening_answers == {"q1": "Yes"}


def test_application_payload_rejects_overlong_cover_letter_and_missing_resume():
    with pytest.raises(ValidationError):
        ApplicationCreate(resume_id="64a123456789abcdef123456", cover_letter="x" * 10001)
    with pytest.raises(ValidationError):
        ApplicationCreate()
