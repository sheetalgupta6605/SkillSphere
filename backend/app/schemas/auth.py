from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator


def validate_password_strength(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be 72 UTF-8 bytes or fewer.")
    if not any(character.isalpha() for character in value) or not any(character.isdigit() for character in value):
        raise ValueError("Password must contain at least one letter and one number.")
    return value


class PasswordFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)

    @field_validator("password", "confirm_password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class CandidateRegisterRequest(PasswordFields):
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return value
    email: EmailStr
    contact_number: str | None = Field(default=None, max_length=40)


class RecruiterRegisterRequest(CandidateRegisterRequest):
    company_name: str = Field(min_length=2, max_length=160)
    company_website: HttpUrl | None = None
    company_location: str = Field(min_length=2, max_length=160)


class RegisterRequest(CandidateRegisterRequest):
    """Temporary compatibility endpoint; public registration never accepts admin."""
    role: str = Field(pattern="^(candidate|recruiter)$")
    company_name: str | None = Field(default=None, min_length=2, max_length=160)
    company_website: HttpUrl | None = None
    company_location: str | None = Field(default=None, min_length=2, max_length=160)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordChangeRequest(PasswordFields):
    current_password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class ResetPasswordRequest(PasswordFields):
    token: str = Field(min_length=32, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    account_status: str = "active"


