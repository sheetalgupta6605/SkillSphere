from datetime import date
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class EducationRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(default_factory=lambda: str(uuid4()))
    degree: str = Field(min_length=1, max_length=120)
    institution: str = Field(min_length=1, max_length=160)
    field_of_study: str = Field(default="", max_length=120)
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)
    graduation_year: int | str | None = None
    currently_studying: bool = False
    score: str = Field(default="", max_length=40)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.setdefault("degree", value.get("qualification", ""))
            value.setdefault("institution", value.get("college", ""))
            value.setdefault("end_year", value.get("graduation_year"))
        return value

    @model_validator(mode="after")
    def valid_year_range(self):
        end = self.end_year or (int(self.graduation_year) if str(self.graduation_year or "").isdigit() else None)
        if not self.currently_studying and self.start_year and end and end < self.start_year:
            raise ValueError("Education end year cannot be before start year")
        return self


class ExperienceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_title: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=160)
    company_name: str | None = Field(default=None, max_length=160)
    employment_type: str = Field(default="Full-time", max_length=40)
    location: str = Field(default="", max_length=120)
    start_date: str = Field(min_length=4, max_length=20)
    end_date: str = Field(default="", max_length=20)
    currently_working: bool = False
    description: str = Field(default="", max_length=3000)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.setdefault("company", value.get("company_name", ""))
        return value

    @model_validator(mode="after")
    def valid_dates(self):
        try:
            start = date.fromisoformat(self.start_date[:10])
            end = date.fromisoformat(self.end_date[:10]) if self.end_date and not self.currently_working else None
        except ValueError as exc:
            raise ValueError("Experience dates must be valid ISO dates") from exc
        if end and end < start:
            raise ValueError("Experience end date cannot be before start date")
        return self


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=3000)
    technologies: list[str] = Field(default_factory=list, max_length=40)
    project_link: HttpUrl | None = None
    github_link: HttpUrl | None = None

    @field_validator("project_link", "github_link", mode="before")
    @classmethod
    def normalize_project_url(cls, value):
        if not value:
            return None
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return None
            if not (val.startswith("http://") or val.startswith("https://")):
                return f"https://{val}"
            return val
        return value

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.setdefault("name", value.get("project_name", ""))
            value.setdefault("technologies", value.get("tech_stack", []))
        return value


class CandidateProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = None
    phone: str | None = Field(default=None, max_length=30)
    date_of_birth: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    headline: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=3000)
    current_job_title: str | None = Field(default=None, max_length=120)
    total_experience: str | None = Field(default=None, max_length=40)
    employment_status: str | None = Field(default=None, max_length=40)
    profile_photo: HttpUrl | None = None
    skills: list[str] = Field(default_factory=list, max_length=100)
    education: list[EducationRecord] = Field(default_factory=list, max_length=30)
    experience: list[ExperienceRecord] = Field(default_factory=list, max_length=50)
    projects: list[ProjectRecord] = Field(default_factory=list, max_length=50)
    certifications: list[dict] = Field(default_factory=list, max_length=50)
    linkedin: HttpUrl | None = None
    github: HttpUrl | None = None
    portfolio: HttpUrl | None = None
    recruiter_discoverable: bool = False

    @field_validator("linkedin", "github", "portfolio", "profile_photo", mode="before")
    @classmethod
    def normalize_profile_url(cls, value):
        if not value:
            return None
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return None
            if not (val.startswith("http://") or val.startswith("https://")):
                return f"https://{val}"
            return val
        return value

    @field_validator("full_name", "phone", "location", "city", "state", "country", "headline", "summary", "current_job_title", "total_experience", "employment_status", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("skills", mode="before")
    @classmethod
    def sanitize_skills_list(cls, values):
        if not isinstance(values, list):
            return []
        normalized = []
        for val in values:
            if isinstance(val, dict):
                s = val.get("name") or val.get("skill") or val.get("title") or ""
            else:
                s = str(val or "")
            normalized.append(s)
        return normalized

    @field_validator("skills")
    @classmethod
    def unique_skills(cls, values):
        unique = {}
        for value in values:
            skill = value.strip()[:80]
            if skill:
                unique.setdefault(skill.casefold(), skill)
        return list(unique.values())

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value):
        if value and (sum(char.isdigit() for char in value) < 7 or any(not (char.isdigit() or char in "+-() .") for char in value)):
            raise ValueError("Enter a valid phone number")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def valid_dob(cls, value):
        if value:
            try:
                if date.fromisoformat(value[:10]) > date.today():
                    raise ValueError("Date of birth cannot be in the future")
            except ValueError as exc:
                raise ValueError("Enter a valid date of birth") from exc
        return value
