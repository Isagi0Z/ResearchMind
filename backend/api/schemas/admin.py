from pydantic import BaseModel, ConfigDict, field_serializer
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class UserListItem(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class UserDetail(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class PaginatedUsersResponse(BaseModel):
    data: List[UserListItem]
    total: int


class UpdateUserRoleRequest(BaseModel):
    role: str


class UpdateUserStatusRequest(BaseModel):
    is_active: bool
