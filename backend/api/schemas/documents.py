from pydantic import BaseModel
from typing import List, Any

class PaginatedDocumentsResponse(BaseModel):
    data: List[Any]
    total: int
