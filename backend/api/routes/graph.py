from fastapi import APIRouter
from backend.api.schemas.graph import GraphDataResponse
from backend.api.mock_graph import generate_mock_graph

router = APIRouter()

@router.get("", response_model=GraphDataResponse)
async def get_graph():
    return generate_mock_graph()

@router.get("/data", response_model=GraphDataResponse)
async def get_graph_data():
    return generate_mock_graph()

@router.get("/node/{id}")
async def get_graph_node(id: str):
    return {"message": "Not implemented detail"}
