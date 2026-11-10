from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_name: str | None = Field(default=None, max_length=160)
    website: str | None = Field(default=None, max_length=300)
    industry: str | None = Field(default=None, max_length=120)
    company_size: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    founded_year: int | None = Field(default=None, ge=1800, le=datetime.now().year)
    company_email: str | None = Field(default=None, max_length=254)
    contact_number: str | None = Field(default=None, max_length=40)
    social_links: dict[str, str] = Field(default_factory=dict)

    @field_validator("company_name", "website", "industry", "company_size", "location", "description", "company_email", "contact_number", mode="before")
    @classmethod
    def trim_values(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("company_email")
    @classmethod
    def valid_email(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid company email address")
        return value

    @field_validator("contact_number")
    @classmethod
    def valid_phone(cls, value):
        if value and (sum(char.isdigit() for char in value) < 7 or any(not (char.isdigit() or char in "+-() .") for char in value)):
            raise ValueError("Enter a valid contact number")
        return value

    @field_validator("social_links")
    @classmethod
    def valid_social_links(cls, links):
        allowed = {"linkedin", "facebook", "instagram", "x", "twitter"}
        if set(links) - allowed or len(links) > 5:
            raise ValueError("Use LinkedIn, Facebook, Instagram, or X links")
        for link in links.values():
            if link and (len(link) > 300 or not link.startswith(("https://", "http://"))):
                raise ValueError("Social links must be valid HTTP(S) URLs")
        return links


class RecruiterProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    designation: str | None = Field(default=None, max_length=120)

    @field_validator("full_name", "phone", "designation", mode="before")
    @classmethod
    def trim_values(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value):
        if value and (sum(char.isdigit() for char in value) < 7 or any(not (char.isdigit() or char in "+-() .") for char in value)):
            raise ValueError("Enter a valid phone number")
        return value
