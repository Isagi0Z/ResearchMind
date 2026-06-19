from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    job_type: str
    status: str
    progress: int
    error_message: Optional[str] = None
    result_reference: Optional[Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    data: list[JobResponse]
    total: int


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str = "queued"
