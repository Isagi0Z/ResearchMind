from fastapi import APIRouter, HTTPException
from backend.api.schemas.graph import GraphDataResponse, GraphNodeResponse
from backend.api.mock_graph import generate_mock_graph

router = APIRouter()

@router.get("", response_model=GraphDataResponse)
async def get_graph():
    return generate_mock_graph()

@router.get("/data", response_model=GraphDataResponse)
async def get_graph_data():
    return generate_mock_graph()

@router.get("/node/{id}", response_model=GraphNodeResponse)
async def get_graph_node(id: str):
    graph = generate_mock_graph()
    for node in graph.nodes:
        if node.id == id:
            return node
    raise HTTPException(status_code=404, detail=f"Node {id} not found")
