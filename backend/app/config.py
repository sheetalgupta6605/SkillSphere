import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIRECTORY / ".env")


class Settings:
    mongodb_url: str | None = os.getenv("MONGODB_URL")
    database_name: str = os.getenv("DATABASE_NAME", "skillsphere_db")

    jwt_secret_key: str | None = os.getenv("JWT_SECRET_KEY")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # FRONTEND_URL can be a single URL or comma-separated list of URLs.
    # Both localhost and 127.0.0.1 variants are added automatically in main.py.

    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv( "GEMINI_MODEL", "gemini-3.5-flash-lite" )

    frontend_url_raw: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    frontend_url: str = frontend_url_raw.split(",")[0].strip()
    frontend_origins: list[str] = [u.strip() for u in frontend_url_raw.split(",") if u.strip()]

    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5"))
    upload_directory: str = os.getenv(
        "UPLOAD_DIRECTORY", str(BACKEND_DIRECTORY / "uploads" / "resumes")
    )


settings = Settings()
