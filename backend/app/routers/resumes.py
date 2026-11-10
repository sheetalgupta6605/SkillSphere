from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_database
from app.database.profiles import find_candidate_profile, update_candidate_profile
from app.dependencies import require_role
from app.services.resume import extract_pages_from_file, parse_resume_text


router = APIRouter(prefix="/api", tags=["Resumes"])
MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 20


class OCRProcessRequest(BaseModel):
    resume_id: str = Field(min_length=1)


def ocr_summary(record: dict) -> str:
    extracted = record.get("extracted_data") or {}
    lines = [f"Resume ID: {record.get('_id', '')}", f"Status: {record.get('status', 'unknown')}", ""]
    for key, value in extracted.items():
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def make_simple_pdf(text: str) -> bytes:
    """Create a small dependency-free PDF for corrected OCR text."""
    lines = text.splitlines()[:45]
    content = ["BT", "/F1 10 Tf", "50 760 Td"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:110]
        content.append(f"({safe}) Tj")
        content.append("0 -16 Td")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


async def process_resume(resume_id: str, file_path: Path, content_type: str, candidate_id: str) -> None:
    db = get_database()
    record_filter = {"_id": ObjectId(resume_id), "candidate_id": candidate_id}
    try:
        await db.resumes.update_one(record_filter, {"$set": {"status": "processing", "error": None}})
        page_texts = extract_pages_from_file(file_path, content_type)
        text = "\n\n".join(page_texts)
        profile = await find_candidate_profile(db, candidate_id) or {}
        known_skills = ["Python", "Java", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI", "Django", "SQL", "PostgreSQL", "MongoDB", "HTML", "CSS", "AWS", "Azure", "Docker", "Git", "Figma", "Excel", "Power BI", "C++", "C#", "Machine Learning", "Data Analysis", "Project Management"]
        known_skills.extend(str(value) for value in profile.get("skills", []) if value)
        extracted = parse_resume_text(text, sorted(set(known_skills)))
        extracted["pages"] = [
            {"page_number": index + 1, "text": page_text[:12000]}
            for index, page_text in enumerate(page_texts)
        ]
        processed_at = datetime.now(timezone.utc)
        await db.resumes.update_one(
            record_filter,
            {"$set": {
                "status": "completed",
                "extracted_data": extracted,
                "processed_at": processed_at,
                "ocr_corrected_at": None,
                "updated_at": processed_at,
                "error": None,
            }},
        )
    except Exception as exc:
        message = str(exc).lower()
        if "tesseract ocr is not installed" in message:
            user_message = "OCR is unavailable on the server. Tesseract must be installed for scanned PDFs."
        elif "no readable text" in message:
            user_message = "No readable text was found. Try a clearer PDF or check that the scan is not blank."
        else:
            user_message = "Text extraction failed. The PDF remains available to preview and download."
        await db.resumes.update_one(
            record_filter,
            {"$set": {"status": "failed", "error": user_message, "processed_at": datetime.now(timezone.utc)}},
        )


def safe_resume_path(stored_name: str) -> Path:
    # Only generated basenames from MongoDB are accepted; never accept a path from the request.
    if not stored_name or Path(stored_name).name != stored_name or "/" in stored_name or "\\" in stored_name:
        raise HTTPException(status_code=404, detail="Resume file is unavailable")
    root = Path(settings.upload_directory).resolve()
    path = (root / stored_name).resolve()
    if path.parent != root:
        raise HTTPException(status_code=404, detail="Resume file is unavailable")
    return path


async def read_pdf_upload(file: UploadFile) -> tuple[str, bytes]:
    filename = (file.filename or "resume.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    filename = "".join(char for char in filename if char.isprintable()).strip()[:180]
    if not filename or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Upload a PDF file only")
    if file.content_type not in {"application/pdf", "application/octet-stream", None}:
        raise HTTPException(status_code=415, detail="Upload a PDF file only")
    data = await file.read(MAX_RESUME_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The selected PDF is empty")
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume must be 5 MB or smaller")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF")
    try:
        import pymupdf as fitz
        document = fitz.open(stream=data, filetype="pdf")
        if document.needs_pass:
            document.close()
            raise HTTPException(status_code=415, detail="Password-protected PDFs are not supported")
        if not document.page_count:
            document.close()
            raise HTTPException(status_code=400, detail="The PDF contains no pages")
        if document.page_count > MAX_PDF_PAGES:
            document.close()
            raise HTTPException(status_code=413, detail=f"PDFs are limited to {MAX_PDF_PAGES} pages")
        document.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The PDF is damaged or cannot be opened") from exc
    return filename, data


def write_resume_file(data: bytes) -> tuple[str, Path]:
    upload_dir = Path(settings.upload_directory).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.pdf"
    stored_path = safe_resume_path(stored_name)
    stored_path.write_bytes(data)
    return stored_name, stored_path

@router.post("/resume/upload", status_code=status.HTTP_202_ACCEPTED)
@router.post("/resumes/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(background_tasks: BackgroundTasks, file: UploadFile = File(...), user=Depends(require_role("candidate")), db=Depends(get_database)):
    filename, data = await read_pdf_upload(file)
    stored_name, stored_path = write_resume_file(data)
    now = datetime.now(timezone.utc)
    record = {"candidate_id": str(user["_id"]), "original_name": filename, "stored_name": stored_name, "content_type": "application/pdf", "size": len(data), "status": "uploaded", "created_at": now, "upload_date": now, "updated_at": now}
    try:
        result = await db.resumes.insert_one(record)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    background_tasks.add_task(process_resume, str(result.inserted_id), stored_path, "application/pdf", str(user["_id"]))
    return {"id": str(result.inserted_id), "status": "processing"}


@router.get("/resumes")
async def list_resumes(user=Depends(require_role("candidate")), db=Depends(get_database)):
    records = await db.resumes.find({"candidate_id": str(user["_id"])}).sort("created_at", -1).to_list(length=50)
    for record in records:
        record["id"] = str(record.pop("_id"))
        record.pop("stored_name", None)
    return records


@router.get("/resumes/me")
async def my_resumes(user=Depends(require_role("candidate")), db=Depends(get_database)):
    return await list_resumes(user, db)


@router.get("/resume/{resume_id}")
@router.get("/resumes/{resume_id}")
async def get_resume(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    record["id"] = str(record.pop("_id"))
    record.pop("stored_name", None)
    return record


@router.get("/resumes/{resume_id}/status")
async def resume_status(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"id": resume_id, "status": record["status"], "extracted_data": record.get("extracted_data"), "error": record.get("error")}


@router.put("/resumes/{resume_id}/ocr")
async def update_ocr_result(resume_id: str, data: dict, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    result = await db.resumes.update_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])}, {"$set": {"extracted_data": data, "ocr_corrected_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"message": "OCR result saved", "id": resume_id, "extracted_data": data}


@router.post("/ocr/process/{resume_id}")
async def process_resume_now(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = safe_resume_path(record.get("stored_name", ""))
    await process_resume(resume_id, path, record["content_type"], str(user["_id"]))
    return await db.resumes.find_one({"_id": ObjectId(resume_id)})


@router.post("/resume/ocr")
async def process_resume_from_request(payload: OCRProcessRequest, background_tasks: BackgroundTasks, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(payload.resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(payload.resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = safe_resume_path(record.get("stored_name", ""))
    await db.resumes.update_one({"_id": ObjectId(payload.resume_id), "candidate_id": str(user["_id"])}, {"$set": {"status": "uploaded", "error": None}})
    background_tasks.add_task(process_resume, payload.resume_id, path, record["content_type"], str(user["_id"]))
    return {"id": payload.resume_id, "status": "processing"}


@router.get("/resumes/{resume_id}/download")
async def download_resume(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = safe_resume_path(record.get("stored_name", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume file is unavailable")
    return FileResponse(path, filename=record["original_name"], media_type=record["content_type"])


@router.get("/resumes/{resume_id}/preview")
async def preview_resume(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = safe_resume_path(record.get("stored_name", ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Resume file is unavailable")
    content_type = record.get("content_type") if record.get("content_type") in {"application/pdf", "image/jpeg", "image/png"} else "application/pdf"
    return Response(path.read_bytes(), media_type=content_type, headers={"Content-Disposition": 'inline; filename="resume.pdf"', "X-Content-Type-Options": "nosniff"})


@router.get("/resumes/{resume_id}/text")
async def resume_text(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    extracted = record.get("extracted_data") or {}
    return {"id": resume_id, "status": record.get("status", "uploaded"), "text": extracted.get("raw_text", ""), "error": record.get("error")}


@router.post("/resumes/{resume_id}/replace", status_code=status.HTTP_202_ACCEPTED)
async def replace_resume(resume_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...), user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record_filter = {"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])}
    existing = await db.resumes.find_one(record_filter)
    if not existing:
        raise HTTPException(status_code=404, detail="Resume not found")
    filename, data = await read_pdf_upload(file)
    new_name, new_path = write_resume_file(data)
    old_path = None
    if existing.get("stored_name"):
        try:
            old_path = safe_resume_path(existing["stored_name"])
        except HTTPException:
            pass
    now = datetime.now(timezone.utc)
    try:
        result = await db.resumes.update_one(record_filter, {"$set": {"original_name": filename, "stored_name": new_name, "content_type": "application/pdf", "size": len(data), "status": "uploaded", "error": None, "extracted_data": None, "processed_at": None, "ocr_corrected_at": None, "upload_date": now, "updated_at": now}})
        if not result.matched_count:
            raise HTTPException(status_code=404, detail="Resume not found")
    except Exception:
        new_path.unlink(missing_ok=True)
        raise
    if old_path and old_path != new_path:
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            pass
    background_tasks.add_task(process_resume, resume_id, new_path, "application/pdf", str(user["_id"]))
    return {"id": resume_id, "status": "processing"}


@router.get("/resumes/{resume_id}/ocr/download.txt")
async def download_ocr_text(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    return PlainTextResponse(ocr_summary(record), headers={"Content-Disposition": f'attachment; filename="resume-{resume_id}-ocr.txt"'})


@router.get("/resumes/{resume_id}/ocr/download.pdf")
async def download_ocr_pdf(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    return Response(content=make_simple_pdf(ocr_summary(record)), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="resume-{resume_id}-ocr.pdf"'})


@router.delete("/resume/{resume_id}")
@router.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    record = await db.resumes.find_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    result = await db.resumes.delete_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])})
    if result.deleted_count:
        try:
            path = safe_resume_path(record.get("stored_name", ""))
            path.unlink(missing_ok=True)
        except HTTPException:
            pass
    return {"message": "Resume deleted"}


@router.put("/resumes/{resume_id}/profile-data")
async def update_resume_data(resume_id: str, data: dict, user=Depends(require_role("candidate")), db=Depends(get_database)):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    result = await db.resumes.update_one({"_id": ObjectId(resume_id), "candidate_id": str(user["_id"])}, {"$set": {"extracted_data": data, "ocr_corrected_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Resume not found")
    profile_update = {}
    for source, target in (("name", "full_name"), ("email", "email"), ("phone", "phone"), ("location", "location"), ("skills", "skills"), ("education", "education"), ("experience", "experience")):
        if data.get(source):
            profile_update[target] = data[source]
    if profile_update:
        await update_candidate_profile(db, str(user["_id"]), profile_update)
        if profile_update.get("full_name"):
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"full_name": str(profile_update["full_name"])}})
    return {"message": "Resume data updated"}


