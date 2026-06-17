from pydantic import BaseModel

class ValidateRequest(BaseModel):
    review_result: dict

class ReviewHistoryResponse(BaseModel):
    id: str
    title: str
    created_at: str
