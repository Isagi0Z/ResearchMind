from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/graph")
async def get_graph():
    raise HTTPException(status_code=501, detail="Not Implemented")

@router.get("/graph/node/{id}")
async def get_graph_node(id: str):
    raise HTTPException(status_code=501, detail="Not Implemented")
