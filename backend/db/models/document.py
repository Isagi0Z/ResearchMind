from sqlalchemy import Column, String, DateTime, func, ForeignKey, Uuid, JSON
import uuid
from backend.db.base import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fingerprint = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(1024), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
