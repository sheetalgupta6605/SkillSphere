# SkillSphere

SkillSphere is a career and recruitment portal for candidates, recruiters, and administrators. It uses React and Vite for the web app, FastAPI for the API, and MongoDB Atlas for persistence.

## Features

- **Candidates:** profile and completion tracking, private resume upload/OCR, job search, saved and recently viewed jobs, applications and status history, messages, notifications, and account settings.
- **Recruiters:** recruiter and company profiles, logo upload, job drafts and approval workflow, applicant review, secure submitted-resume access, status updates, and interview scheduling.
- **Administrators:** user and company review, job approvals, application overview, platform reports, and notifications.
- **Matching:** the current resume-to-job matcher is a local, weighted comparison of extracted resume evidence and job requirements. It saves analysis history in MongoDB. **It does not call an external AI model/API**, so do not describe its scores as AI-generated. External AI integration and its live verification remain outstanding.

## Technology and layout

- Python, FastAPI, asynchronous PyMongo, MongoDB Atlas
- JavaScript, React, React Router, Vite, CSS
- Local PDF text extraction; optional Tesseract OCR for scanned PDFs

```text
backend/app/routers/       FastAPI endpoints and authorization
backend/app/services/      Resume extraction and local matching
backend/app/database/      MongoDB connection, profiles, and indexes
backend/app/schemas/       Request and response validation
frontend/src/pages/        Candidate, recruiter, and admin screens
frontend/src/components/   Shared navigation and UI components
```

## Requirements

- Python 3.11 or newer
- Node.js and npm
- A MongoDB Atlas cluster and database user
- Tesseract OCR only if scanned resumes need OCR

## Configure MongoDB Atlas and the API

From PowerShell:

```powershell
cd C:\Users\sheet\OneDrive\Desktop\SkillSphere\backend
Copy-Item .env.example .env
```

Edit `backend/.env` and set `MONGODB_URL` to the Atlas connection string and `DATABASE_NAME` to the project database name. Set `JWT_SECRET_KEY` to a private random value with at least 32 bytes. The example file contains placeholders only. Never put credentials in frontend environment variables or commit `.env`.

The API creates required collections and indexes at startup. The server must be able to reach the Atlas cluster and the cluster access list must allow the development machine.

## Run the backend

```powershell
cd C:\Users\sheet\OneDrive\Desktop\SkillSphere\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

API documentation: [http://localhost:8000/docs](http://localhost:8000/docs). Liveness endpoint: [http://localhost:8000/health](http://localhost:8000/health).

## Run the frontend

In a second PowerShell window:

```powershell
cd C:\Users\sheet\OneDrive\Desktop\SkillSphere\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The frontend defaults to `http://localhost:8000` for the API. Change `VITE_API_URL` in `frontend/.env` only if the backend is hosted elsewhere. Backend secrets must never use a `VITE_` variable.

## Environment variables

Backend settings are read from `backend/.env`: `MONGODB_URL`, `DATABASE_NAME`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `FRONTEND_URL`, `MAX_UPLOAD_SIZE_MB`, and `UPLOAD_DIRECTORY`. `TESSERACT_CMD` is optional for scanned documents.

Frontend setting: `VITE_API_URL` in `frontend/.env`.

## API and data

FastAPI routes are grouped under `/api`: authentication, candidate profiles, jobs, resumes, matching history, applications, recruiter management, companies, administration, notifications, and messages. MongoDB stores users, candidate/recruiter profiles, companies, jobs, resumes, analyses, applications, notifications, saved jobs, and job views. Private resume files are kept under the backend upload directory and served only through ownership-checked endpoints; company logos are public assets.

## Testing

From the project root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest tests -q -p no:cacheprovider
python -m compileall -q app
```

Then verify the frontend bundle:

```powershell
cd ..\frontend
npm run build
```

Automated tests and a production build do not replace a live Atlas and browser workflow check. Phase 15 has not passed end-to-end verification until Atlas connectivity and actual AI-provider integration are configured and exercised.

## Screenshots

Add screenshots of the candidate, recruiter, and admin workspaces here after verifying them against a live database.

## Future improvements

- Integrate a real AI provider for resume analysis and resume-to-job matching, with explicit data-transfer approval, backend-only credentials, response validation, and timeout/rate-limit handling.
- Add authenticated browser testing for all three role workflows and small-screen layouts.
- Add database backup, retention, and operational monitoring policies.
