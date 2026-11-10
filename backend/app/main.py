from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_database, connect_to_database
from app.database.indexes import create_indexes
from app.routers import admin, applications, auth, candidates, companies, health, jobs, matching, messages, notifications, realtime, recruiter, resumes, resume_search


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await connect_to_database()
        await create_indexes()
        yield
    finally:
        await close_database()


app = FastAPI(title="SkillSphere API", description="Career and job portal API backed by MongoDB.", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.frontend_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(jobs.router)
app.include_router(resumes.router)
app.include_router(matching.router)
app.include_router(matching.job_match_router)
app.include_router(matching.resume_analysis_router)
app.include_router(recruiter.router)
app.include_router(resume_search.router)
app.include_router(companies.router)
app.include_router(admin.router)
app.include_router(applications.router)
app.include_router(notifications.router)
app.include_router(messages.router)
app.include_router(realtime.router)


