from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

class GraphNodeData(BaseModel):
    label: str
    type: Literal['entity', 'document', 'theme', 'cluster']
    confidence: Optional[float] = None
    relatedDocuments: Optional[int] = None
    title: Optional[str] = None
    year: Optional[int] = None
    authors: Optional[List[str]] = None
    size: Optional[int] = None
    containedEntities: Optional[List[str]] = None

class GraphEdgeData(BaseModel):
    type: Literal['USES_METHOD', 'COMPARES_WITH', 'SUPPORTS', 'CONTRADICTS', 'REFERENCES', 'CO_OCCURS']
    confidence: Optional[float] = None

class GraphNodeResponse(BaseModel):
    id: str
    type: str
    position: Dict[str, float]
    data: GraphNodeData

class GraphEdgeResponse(BaseModel):
    id: str
    source: str
    target: str
    type: str
    data: GraphEdgeData
    animated: Optional[bool] = False

class GraphDataResponse(BaseModel):
    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]
