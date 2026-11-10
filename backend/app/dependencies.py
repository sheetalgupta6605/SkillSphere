from collections.abc import AsyncGenerator

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.database import get_database
from app.utils.auth import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def database_dependency() -> AsyncGenerator:
    yield get_database()


async def current_user(token: str = Depends(oauth2_scheme), db=Depends(database_dependency)):
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id or not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    if not user.get("is_active", True) or user.get("account_status", "active") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    if payload.get("ver", 0) != user.get("auth_version", 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired. Please sign in again.")
    # Authorization always uses the role loaded from MongoDB, not the JWT claim.
    return user


def require_role(*roles: str):
    async def role_dependency(user=Depends(current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return role_dependency
