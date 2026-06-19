from sqlalchemy import Column, String, Integer, DateTime, JSON, func
from backend.db.base import Base


class CorpusDocument(Base):
    __tablename__ = "corpus_documents"

    ruo_id = Column(String(255), primary_key=True)
    title = Column(String(1024), nullable=False)
    authors_json = Column(JSON, nullable=True)
    year = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="success")
    entity_count = Column(Integer, nullable=False, default=0)
    source = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
