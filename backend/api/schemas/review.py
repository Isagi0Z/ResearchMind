from pydantic import BaseModel

class ValidateRequest(BaseModel):
    review_result: dict # Would ideally be ReviewResult, but we can accept dict and parse it
