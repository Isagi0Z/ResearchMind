from fastapi import APIRouter
from backend.api.config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/version")
async def get_version():
    return {"version": settings.VERSION}
