# SkillSphere API

The backend uses FastAPI, asynchronous PyMongo, and MongoDB.

## Setup

1. Copy `.env.example` to `.env` and set `MONGODB_URL` and `JWT_SECRET_KEY`.
2. Create or activate the virtual environment.
3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Start the API from the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

From the SkillSphere project root, you can also run `python backend/run.py`, execute `start-backend.ps1`, or use the `SkillSphere FastAPI` VS Code launch profile.

Swagger documentation is available at `http://localhost:8000/docs`.

## Current API foundation

- `GET /health`
- Candidate and recruiter registration
- JWT login and current-user lookup
- Candidate profile read/update
- Recruiter job creation
- Published job search and details
- Candidate job applications with duplicate prevention
- Job filters, sorting, pagination, saved jobs, and recruiter-owned CRUD
- Application tracking and withdrawal
- Recruiter applicant status management
- Admin analytics and user activation controls
- Personal notification listing and read updates (`/api/notifications`)
- Direct-message inbox, conversation history, and sending (`/api/messages`)
- Authenticated realtime message events (`/ws`, authenticate with a first WebSocket message containing the access token)
- Resume aliases `POST /api/resume/upload`, `POST /api/resume/ocr`, `GET /api/resume/{id}`, and `DELETE /api/resume/{id}`; plural `/api/resumes` routes remain available for the current frontend.
- Candidate resume-to-job analysis: `POST /api/resume-analysis/analyze/{job_id}`, `GET /api/resume-analysis/me`, `GET /api/resume-analysis/{analysis_id}`, and candidate-owned analysis deletion. Matching uses local extracted resume text and explainable weighted criteria; no external AI service is used.
- Recruiter workspace: `GET /api/recruiter/dashboard` returns recruiter-owned job/application stats and recent activity; `GET/PUT /api/recruiter/profile` updates only permitted recruiter details.
- Company profile: `GET/PUT /api/companies/me` and recruiter-only `POST /api/companies/logo` (PNG/JPEG/WebP, maximum 2 MB). Uploaded logos are served from the isolated public company-logo route; private resume uploads remain unexposed.
- Secure candidate-only resume management: `GET /api/resumes/me`, `POST /api/resumes/upload`, `POST /api/resumes/{id}/replace`, `GET /api/resumes/{id}/preview`, `GET /api/resumes/{id}/download`, `GET /api/resumes/{id}/text`, and `DELETE /api/resumes/{id}`.
- Candidate applications: `POST /api/applications/{job_id}/apply`, `GET /api/applications/me`, `GET /api/applications/{application_id}`, and `POST /api/applications/{application_id}/withdraw` (legacy PUT withdrawal remains available). Applications require a completed candidate-owned resume; an optional saved resume analysis is attached with its actual score snapshot.

MongoDB indexes are created during application startup.

Resume uploads accept PDF only (5 MB, 20 pages maximum) and are stored under the private backend upload directory. PyMuPDF extracts ordinary PDF text; scanned PDFs use local Tesseract OCR via Pytesseract and Pillow. OCR runs only when no usable page text is available. Extracted text and status are stored in the existing `resumes` collection.

### Windows resume OCR setup

From PowerShell in the `backend` folder:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

To install only the resume processing libraries into the active environment:

```powershell
python -m pip install PyMuPDF Pillow pytesseract python-multipart
```

Tesseract itself is a separate Windows program. Install the Windows build linked from the [official Tesseract downloads documentation](https://tesseract-ocr.github.io/tessdoc/Downloads), which points Windows users to UB Mannheim's installer. Then either add its install folder to Windows `PATH`, or set this in `backend/.env` (edit the path if installed elsewhere):

```dotenv
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

Restart FastAPI after changing `.env`. Scanned-PDF OCR requires Tesseract to be installed; text-based PDFs do not.
