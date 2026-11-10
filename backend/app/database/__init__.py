from pymongo import AsyncMongoClient
from pymongo.errors import (
    ConfigurationError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from app.config import settings


client: AsyncMongoClient | None = None
database = None


async def connect_to_database() -> None:
    global client, database

    if not settings.mongodb_url:
        raise RuntimeError("MONGODB_URL is missing from backend/.env.")

    client = AsyncMongoClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=5000,
    )

    try:
        await client.admin.command("ping")

        database = client[settings.database_name]

        print("MongoDB Atlas connected successfully!")
        print(f"Database: {settings.database_name}")

    except OperationFailure as exc:
        await client.close()
        client = None
        database = None

        if getattr(exc, "code", None) == 8000 or "authentication failed" in str(exc).lower():
            raise RuntimeError(
                "MongoDB Atlas authentication failed. Check the Database Access username and password."
            ) from exc

        raise RuntimeError(
            "MongoDB rejected the connection. Check Atlas settings and database user permissions."
        ) from exc

    except ServerSelectionTimeoutError as exc:
        await client.close()
        client = None
        database = None

        raise RuntimeError(
            "MongoDB Atlas is unreachable. Check the cluster hostname, IP access list, and network."
        ) from exc

    except ConfigurationError as exc:
        await client.close()
        client = None
        database = None

        raise RuntimeError(
            "MongoDB hostname could not be resolved. Check your Atlas connection string."
        ) from exc

    except PyMongoError as exc:
        await client.close()
        client = None
        database = None

        raise RuntimeError(
            "MongoDB connection failed. Check MONGODB_URL and Atlas settings."
        ) from exc


async def close_database() -> None:
    global client, database

    if client is not None:
        await client.close()

    client = None
    database = None

    print("MongoDB connection closed.")


def get_database():
    if database is None:
        raise RuntimeError("Database is not connected.")

    return database