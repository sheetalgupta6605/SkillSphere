import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIRECTORY / ".env")

class Settings:
    mongodb_url = os.getenv("MONGODB_URL")
    database_name = os.getenv("DATABASE_NAME", "skillsphere_db")

    jwt_secret_key = os.getenv("JWT_SECRET_KEY")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    gemini_api_key = os.getenv("GEMINI_API_KEY")

    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    _frontend_url_raw = os.getenv("FRONTEND_URL", "http://localhost:5173,http://127.0.0.1:5173")
    frontend_url: str = _frontend_url_raw.split(",")[0].strip()
    frontend_origins: list[str] = [u.strip() for u in _frontend_url_raw.split(",") if u.strip()]
    
    max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5"))
    upload_directory = os.getenv("UPLOAD_DIRECTORY", str(BACKEND_DIRECTORY / "uploads" / "resumes"))
    

settings = Settings()
