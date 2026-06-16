from sqlalchemy import Column, String, DateTime, func, ForeignKey, Uuid, JSON
import uuid
from backend.db.base import Base

class Query(Base):
    __tablename__ = "queries"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_query = Column(String, nullable=False)
    query_type = Column(String(100), nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
