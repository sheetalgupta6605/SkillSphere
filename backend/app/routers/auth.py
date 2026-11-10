from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database import get_database
from app.dependencies import current_user
from app.services.notifications import create_notification
from app.schemas.auth import (
    CandidateRegisterRequest,
    ForgotPasswordRequest,
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    RecruiterRegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.utils.auth import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def user_response(user: dict) -> UserResponse:
    account_status = user.get("account_status", "active")
    is_active = bool(user.get("is_active", True)) and account_status == "active"
    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        is_active=is_active,
        account_status=account_status,
    )


async def _create_user(payload, role: str, db, company_data: dict | None = None) -> UserResponse:
    email = str(payload.email).strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email is already registered")

    now = datetime.now(timezone.utc)
    user_id = ObjectId()
    user = {
        "_id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name.strip(),
        "role": role,
        "is_active": True,
        "account_status": "active",
        "auth_version": 0,
        "created_at": now,
        "updated_at": now,
    }
    inserted_user = inserted_profile = inserted_legacy = inserted_company = False
    profile_id = ObjectId()
    legacy_id = ObjectId()
    company_id = ObjectId() if company_data else None

    try:
        await db.users.insert_one(user)
        inserted_user = True
        if role == "candidate":
            profile = {
                "_id": profile_id,
                "candidate_id": str(profile_id),
                "user_id": str(user_id),
                "email": email,
                "full_name": user["full_name"],
                "contact_number": payload.contact_number,
                "contact_details": {"phone": payload.contact_number} if payload.contact_number else {},
                "education": [],
                "experience": [],
                "projects": [],
                "certifications": [],
                "skills": [],
                "created_at": now,
                "updated_at": now,
            }
            await db.candidates.insert_one(profile)
            inserted_profile = True
            # Keep the existing frontend's profile collection in sync during migration.
            await db.candidate_profiles.insert_one({
                "_id": legacy_id,
                "user_id": str(user_id),
                "email": email,
                "full_name": user["full_name"],
                "contact_number": payload.contact_number,
                "skills": [],
                "created_at": now,
                "updated_at": now,
            })
            inserted_legacy = True
        else:
            company = {
                "_id": company_id,
                "company_id": str(company_id),
                "recruiter_id": str(user_id),
                "company_name": company_data["company_name"].strip(),
                "website": str(company_data["company_website"]) if company_data.get("company_website") else None,
                "location": company_data["company_location"].strip(),
                "description": "",
                "contact_information": {"email": email, "phone": payload.contact_number},
                "created_at": now,
                "updated_at": now,
            }
            await db.companies.insert_one(company)
            inserted_company = True
            recruiter_id = ObjectId()
            await db.recruiters.insert_one({
                "_id": recruiter_id,
                "recruiter_id": str(recruiter_id),
                "user_id": str(user_id),
                "company_id": str(company_id),
                "designation": "",
                "contact_number": payload.contact_number,
                "recruiter_details": {},
                "created_at": now,
                "updated_at": now,
            })
            inserted_profile = True
            await db.recruiter_profiles.insert_one({
                "_id": legacy_id,
                "user_id": str(user_id),
                "email": email,
                "full_name": user["full_name"],
                "company_id": str(company_id),
                "created_at": now,
                "updated_at": now,
            })
            inserted_legacy = True
    except DuplicateKeyError as exc:
        if inserted_legacy:
            await (db.candidate_profiles if role == "candidate" else db.recruiter_profiles).delete_one({"_id": legacy_id})
        if inserted_profile:
            await (db.candidates if role == "candidate" else db.recruiters).delete_one({"_id": profile_id if role == "candidate" else recruiter_id})
        if inserted_company:
            await db.companies.delete_one({"_id": company_id})
        if inserted_user:
            await db.users.delete_one({"_id": user_id})
        raise HTTPException(status_code=409, detail="Email is already registered") from exc
    except Exception as exc:
        try:
            if inserted_legacy:
                await (db.candidate_profiles if role == "candidate" else db.recruiter_profiles).delete_one({"_id": legacy_id})
            if inserted_profile:
                await (db.candidates if role == "candidate" else db.recruiters).delete_one({"_id": profile_id if role == "candidate" else recruiter_id})
            if inserted_company:
                await db.companies.delete_one({"_id": company_id})
            if inserted_user:
                await db.users.delete_one({"_id": user_id})
        except PyMongoError:
            raise HTTPException(status_code=503, detail="Registration could not be completed; contact support to verify account setup") from exc
        raise
    return user_response(user)


@router.post("/register/candidate", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_candidate(payload: CandidateRegisterRequest, db=Depends(get_database)):
    return await _create_user(payload, "candidate", db)


@router.post("/register/recruiter", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_recruiter(payload: RecruiterRegisterRequest, db=Depends(get_database)):
    company = {
        "company_name": payload.company_name,
        "company_website": payload.company_website,
        "company_location": payload.company_location,
    }
    result = await _create_user(payload, "recruiter", db, company)
    await notify_admins_recruiter_registration(db, result)
    return result


async def notify_admins_recruiter_registration(db, recruiter):
    admins = await db.users.find({"role": "admin", "is_active": {"$ne": False}}).to_list(length=100)
    for admin in admins:
        await create_notification(db, str(admin["_id"]), "New recruiter registration", f"{recruiter.full_name} registered as a recruiter.", "recruiter_registered", recruiter.id, "/admin-users")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, deprecated=True)
async def register_legacy(payload: RegisterRequest, db=Depends(get_database)):
    if payload.role == "candidate":
        return await _create_user(payload, "candidate", db)
    if not payload.company_name or not payload.company_location:
        raise HTTPException(status_code=422, detail="Recruiter registration requires company name and location")
    company = {
        "company_name": payload.company_name,
        "company_website": payload.company_website,
        "company_location": payload.company_location,
    }
    result = await _create_user(payload, "recruiter", db, company)
    await notify_admins_recruiter_registration(db, result)
    return result


async def _authenticate(email: str, password: str, db) -> TokenResponse:
    user = await db.users.find_one({"email": email.strip().lower()})
    if not user or not user.get("password_hash") or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", True) or user.get("account_status", "active") != "active":
        raise HTTPException(status_code=403, detail="Account is disabled")
    return TokenResponse(
        access_token=create_access_token(str(user["_id"]), user["role"], user.get("auth_version", 0)),
        user=user_response(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db=Depends(get_database)):
    return await _authenticate(str(payload.email), payload.password, db)


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
async def token(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_database)):
    """OAuth2 form endpoint used by Swagger's Authorize dialog."""
    return await _authenticate(form_data.username, form_data.password, db)


@router.post("/logout")
async def logout(user: dict = Depends(current_user), db=Depends(get_database)):
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$inc": {"auth_version": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(current_user)):
    return user_response(user)


@router.put("/change-password")
async def change_password(payload: PasswordChangeRequest, user: dict = Depends(current_user), db=Depends(get_database)):
    if not verify_password(payload.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(payload.password), "updated_at": datetime.now(timezone.utc)}, "$inc": {"auth_version": 1}},
    )
    return {"message": "Password changed. Please sign in again."}


@router.post("/forgot-password")
async def forgot_password(_: ForgotPasswordRequest):
    raise HTTPException(
        status_code=503,
        detail="Password reset email delivery is not configured. Ask an administrator to configure email before requesting a reset.",
    )


@router.post("/reset-password")
async def reset_password(_: ResetPasswordRequest):
    raise HTTPException(
        status_code=503,
        detail="Password reset email delivery is not configured. Ask an administrator to configure email before resetting a password.",
    )
