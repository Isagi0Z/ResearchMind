from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/monitoring")
async def get_monitoring():
    raise HTTPException(status_code=501, detail="Not Implemented")
