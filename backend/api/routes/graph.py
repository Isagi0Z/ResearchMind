from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from backend.api.schemas.graph import GraphDataResponse, GraphNodeResponse
from backend.api.services.graph_service import GraphService
from backend.api.dependencies import get_corpus_manager

router = APIRouter()

def _get_graph_service(corpus=Depends(get_corpus_manager)) -> GraphService:
    return GraphService(corpus)

@router.get("", response_model=GraphDataResponse)
async def get_graph(
    nodeType: Optional[str] = Query(None, alias="nodeType"),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    service: GraphService = Depends(_get_graph_service),
):
    return service.get_graph(
        node_type=nodeType,
        search=search,
        offset=offset,
        limit=limit,
    )

@router.get("/data", response_model=GraphDataResponse)
async def get_graph_data(
    nodeType: Optional[str] = Query(None, alias="nodeType"),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    service: GraphService = Depends(_get_graph_service),
):
    return service.get_graph(
        node_type=nodeType,
        search=search,
        offset=offset,
        limit=limit,
    )

@router.get("/node/{id}", response_model=GraphNodeResponse)
async def get_graph_node(
    id: str,
    service: GraphService = Depends(_get_graph_service),
):
    node = service.get_node(id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {id} not found")
    return node
