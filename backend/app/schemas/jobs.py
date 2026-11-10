from datetime import datetime, timezone

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=20, max_length=10000)
    category: str | None = Field(default=None, max_length=100)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    additional_requirements: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    location: str = Field(min_length=2, max_length=160)
    experience_range: str | None = Field(default=None, max_length=80)
    job_type: Literal["full-time", "part-time", "internship", "contract"] = "full-time"
    work_mode: Literal["remote", "hybrid", "on-site"] | None = None
    salary_range: str | None = Field(default=None, max_length=80)
    salary_min: int | None = Field(default=None, ge=0)
    number_of_openings: int = Field(default=1, ge=1, le=10000)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    screening_questions: list[dict] = Field(default_factory=list, max_length=20)
    application_deadline: datetime | None = None

    @field_validator("title", "description", "location", mode="before")
    @classmethod
    def trim_required_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("required_skills", "preferred_skills", "responsibilities", "requirements", "additional_requirements", "education_requirements")
    @classmethod
    def clean_lists(cls, values):
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    @field_validator("application_deadline")
    @classmethod
    def deadline_is_future(cls, value):
        if value:
            aware_value = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            if aware_value <= datetime.now(timezone.utc):
                raise ValueError("Application deadline must be in the future")
        return value


class JobResponse(JobCreate):
    id: str
    recruiter_id: str
    status: str
    created_at: datetime
