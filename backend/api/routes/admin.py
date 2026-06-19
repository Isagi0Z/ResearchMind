from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.session import get_db
from backend.api.dependencies import require_role
from backend.db.models.user import User
from backend.api.schemas.admin import (
    PaginatedUsersResponse,
    UserDetail,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
)
from backend.api.services.admin_service import AdminService

router = APIRouter()


def _user_to_detail(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


async def _get_admin_service(
    db: AsyncSession = Depends(get_db),
) -> AdminService:
    return AdminService(db)


@router.get("/users", response_model=PaginatedUsersResponse)
async def list_users(
    pageIndex: int = Query(0, ge=0, alias="pageIndex"),
    pageSize: int = Query(10, ge=1, le=100, alias="pageSize"),
    searchQuery: Optional[str] = Query(None, alias="searchQuery"),
    sortBy: str = Query("created_at", alias="sortBy"),
    sortDirection: str = Query("desc", alias="sortDirection"),
    current_user: User = Depends(require_role("admin")),
    service: AdminService = Depends(_get_admin_service),
):
    users, total = await service.list_users(
        search_query=searchQuery,
        page_index=pageIndex,
        page_size=pageSize,
        sort_by=sortBy,
        sort_direction=sortDirection,
    )
    return PaginatedUsersResponse(
        data=[UserDetail.model_validate(_user_to_detail(u)) for u in users],
        total=total,
    )


@router.get("/users/{id}", response_model=UserDetail)
async def get_user(
    id: str,
    current_user: User = Depends(require_role("admin")),
    service: AdminService = Depends(_get_admin_service),
):
    user = await service.get_user(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetail.model_validate(_user_to_detail(user))


@router.patch("/users/{id}/role", response_model=UserDetail)
async def update_user_role(
    id: str,
    body: UpdateUserRoleRequest,
    current_user: User = Depends(require_role("admin")),
    service: AdminService = Depends(_get_admin_service),
):
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'user' or 'admin'.")
    user = await service.update_role(id, body.role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetail.model_validate(_user_to_detail(user))


@router.patch("/users/{id}/status", response_model=UserDetail)
async def update_user_status(
    id: str,
    body: UpdateUserStatusRequest,
    current_user: User = Depends(require_role("admin")),
    service: AdminService = Depends(_get_admin_service),
):
    user = await service.update_status(id, body.is_active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetail.model_validate(_user_to_detail(user))
