from sqlalchemy import Column, String, DateTime, func, ForeignKey, Uuid, Integer, Text
import uuid
from backend.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="queued", index=True)
    progress = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    result_reference = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
