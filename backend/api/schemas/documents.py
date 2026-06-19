from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ruo_id: str
    title: str
    authors: List[str] = []
    year: Optional[int] = None
    status: str = "success"
    entity_count: int = 0
    source: Optional[str] = None


class DocumentDetail(BaseModel):
    ruo_id: str
    title: str
    authors: List[str] = []
    year: Optional[int] = None
    status: str = "success"
    entity_count: int = 0
    source: Optional[str] = None
    abstract: Optional[str] = None
    pipeline_stages: List[str] = []


class PaginatedDocumentsResponse(BaseModel):
    data: List[DocumentListItem]
    total: int
