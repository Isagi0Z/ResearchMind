from pydantic import BaseModel
from typing import Any, Dict, List

class ParseRequest(BaseModel):
    raw_query: str

class AnswerRequest(BaseModel):
    query_id: str
    raw_query: str

class QueryHistoryResponse(BaseModel):
    id: str
    raw_query: str
    query_type: str
    created_at: str
