from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard():
    raise HTTPException(status_code=501, detail="Not Implemented")
