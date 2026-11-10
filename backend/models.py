from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    CANDIDATE = "candidate"
    RECRUITER = "recruiter"
    ADMIN = "admin"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    UNDER_REVIEW = "under_review"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    SELECTED = "selected"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class MongoDocument(BaseModel):
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)


class UserDocument(MongoDocument):
    email: str
    full_name: str = Field(min_length=2, max_length=120)
    role: UserRole
    is_active: bool = True


class ApplicationDocument(MongoDocument):
    candidate_id: str
    job_id: str
    status: ApplicationStatus = ApplicationStatus.APPLIED
