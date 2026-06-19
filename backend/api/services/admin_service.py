from typing import Optional, Tuple, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from backend.db.models.user import User


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(
        self,
        search_query: Optional[str] = None,
        page_index: int = 0,
        page_size: int = 10,
        sort_by: str = "created_at",
        sort_direction: str = "desc",
    ) -> Tuple[List[User], int]:
        query = select(User)
        count_query = select(func.count(User.id))

        if search_query:
            like = f"%{search_query}%"
            filter_cond = or_(User.username.ilike(like), User.email.ilike(like))
            query = query.where(filter_cond)
            count_query = count_query.where(filter_cond)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        sort_column = getattr(User, sort_by, User.created_at)
        if sort_direction == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        query = query.offset(page_index * page_size).limit(page_size)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def get_user(self, user_id: str) -> Optional[User]:
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        result = await self.db.execute(select(User).where(User.id == uid))
        return result.scalar_one_or_none()

    async def update_role(self, user_id: str, role: str) -> Optional[User]:
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        result = await self.db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user:
            return None
        user.role = role
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_status(self, user_id: str, is_active: bool) -> Optional[User]:
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        result = await self.db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user:
            return None
        user.is_active = is_active
        await self.db.commit()
        await self.db.refresh(user)
        return user
