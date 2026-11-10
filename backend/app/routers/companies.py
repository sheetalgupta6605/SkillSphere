from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.database import get_database
from app.dependencies import require_role
from app.schemas.recruiter import CompanyProfileUpdate

router = APIRouter(prefix="/api/companies", tags=["Companies"])
LOGO_DIR = Path(settings.upload_directory).parent / "company_logos"
MAX_LOGO_BYTES = 2 * 1024 * 1024
IMAGE_TYPES = {
    "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/webp": (".webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
}


def serialize(company: dict | None, user: dict) -> dict | None:
    if not company:
        return None
    result = dict(company)
    result["id"] = str(result.pop("_id", result.get("company_id", "")))
    contact = result.get("contact_information") or {}
    result.setdefault("company_email", contact.get("email") or user.get("email"))
    result.setdefault("contact_number", contact.get("phone") or user.get("contact_number", ""))
    result.setdefault("social_links", {})
    return result


@router.get("/me")
async def get_my_company(user=Depends(require_role("recruiter")), db=Depends(get_database)):
    return serialize(await db.companies.find_one({"recruiter_id": str(user["_id"])}), user)


@router.put("/me")
async def update_my_company(payload: CompanyProfileUpdate, user=Depends(require_role("recruiter")), db=Depends(get_database)):
    updates = payload.model_dump(exclude_unset=True)
    if "company_name" in updates and not updates["company_name"]:
        raise HTTPException(status_code=422, detail="Company name is required.")
    updates["recruiter_id"] = str(user["_id"])
    updates["updated_at"] = datetime.now(timezone.utc)
    if "company_email" in updates or "contact_number" in updates:
        existing = await db.companies.find_one({"recruiter_id": str(user["_id"])}) or {}
        contact = dict(existing.get("contact_information") or {})
        if "company_email" in updates:
            contact["email"] = updates.pop("company_email")
        if "contact_number" in updates:
            contact["phone"] = updates.pop("contact_number")
        updates["contact_information"] = contact
    await db.companies.update_one({"recruiter_id": str(user["_id"])}, {"$set": updates, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)
    return serialize(await db.companies.find_one({"recruiter_id": str(user["_id"])}), user)


@router.post("/logo")
async def upload_company_logo(file: UploadFile = File(...), user=Depends(require_role("recruiter")), db=Depends(get_database)):
    content_type = (file.content_type or "").lower()
    metadata = IMAGE_TYPES.get(content_type)
    if not metadata:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, or WebP company logo.")
    data = await file.read(MAX_LOGO_BYTES + 1)
    if not data or len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="Company logo must be 2 MB or smaller.")
    extension, signature_check = metadata
    if not signature_check(data):
        raise HTTPException(status_code=415, detail="The uploaded file does not match its image type.")
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    (LOGO_DIR / filename).write_bytes(data)
    logo_url = f"/api/companies/logos/{filename}"
    now = datetime.now(timezone.utc)
    await db.companies.update_one({"recruiter_id": str(user["_id"])}, {"$set": {"recruiter_id": str(user["_id"]), "logo_url": logo_url, "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
    return {"logo_url": logo_url}


@router.get("/logos/{filename}")
async def get_company_logo(filename: str):
    if "/" in filename or "\\" in filename or not filename.endswith((".png", ".jpg", ".webp")):
        raise HTTPException(status_code=404, detail="Logo not found")
    path = LOGO_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path)
