from pydantic import BaseModel
from typing import Any, Dict

class ParseRequest(BaseModel):
    raw_query: str

class AnswerRequest(BaseModel):
    query_id: str
    raw_query: str
