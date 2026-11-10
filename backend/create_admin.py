"""Create the first SkillSphere administrator securely.

Run this file from the backend directory. It uses the same MongoDB settings
and bcrypt password hashing function as the application.
"""

import asyncio
from datetime import datetime, timezone
from getpass import getpass

from pymongo import AsyncMongoClient
from pymongo.errors import ConfigurationError, OperationFailure, PyMongoError, ServerSelectionTimeoutError

from app.config import settings
from app.utils.auth import hash_password


def read_required(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError("This value is required.")
    return value


async def create_admin() -> None:
    if not settings.mongodb_url:
        raise RuntimeError("MONGODB_URL is missing from backend/.env.")

    email = read_required("Admin email: ").lower()
    full_name = read_required("Admin full name: ")
    password = getpass("Admin password: ")
    password_confirmation = getpass("Confirm admin password: ")

    password_size = len(password.encode("utf-8"))
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if password_size > 72:
        raise ValueError("Password must be 72 UTF-8 bytes or fewer because bcrypt has a 72-byte limit.")
    if password != password_confirmation:
        raise ValueError("Passwords do not match.")

    client = AsyncMongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        database = client[settings.database_name]

        existing_user = await database.users.find_one({"email": email})
        if existing_user:
            if existing_user.get("role") == "admin":
                raise RuntimeError("An admin account with this email already exists.")
            raise RuntimeError("This email already belongs to a non-admin account. Use a different email.")

        await database.users.insert_one(
            {
                "email": email,
                "password_hash": hash_password(password),
                "full_name": full_name,
                "role": "admin",
                "is_active": True,
                "account_status": "active",
                "auth_version": 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        print("Admin account created successfully.")
        print("You can now log in through POST /api/auth/login or the Swagger UI.")
    except OperationFailure as exc:
        if getattr(exc, "code", None) == 8000 or "authentication failed" in str(exc).lower():
            raise RuntimeError("MongoDB Atlas authentication failed. Check the Database Access credentials in backend/.env.") from exc
        raise RuntimeError("MongoDB rejected the admin creation request.") from exc
    except ServerSelectionTimeoutError as exc:
        raise RuntimeError("MongoDB Atlas is unreachable. Check the cluster hostname, IP access list, and network connection.") from exc
    except ConfigurationError as exc:
        raise RuntimeError("MongoDB Atlas hostname could not be resolved. Copy a fresh mongodb+srv URI from Atlas.") from exc
    except PyMongoError as exc:
        raise RuntimeError("MongoDB operation failed. Check the Atlas connection settings.") from exc
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(create_admin())
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")


