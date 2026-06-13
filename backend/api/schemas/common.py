from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str

class ErrorResponse(BaseModel):
    error: ErrorDetail

class ResponseModel(BaseModel, Generic[T]):
    data: T
    meta: Optional[dict[str, Any]] = None
