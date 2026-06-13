from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/documents")
async def get_documents():
    raise HTTPException(status_code=501, detail="Not Implemented")

@router.get("/document/{id}")
async def get_document(id: str):
    raise HTTPException(status_code=501, detail="Not Implemented")
