from fastapi import APIRouter


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "success",
        "message": "SkillSphere backend is running",
    }
