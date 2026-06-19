from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, asc
from backend.db.models.corpus_document import CorpusDocument
from backend.api.schemas.documents import DocumentListItem, DocumentDetail, PaginatedDocumentsResponse
from researchmind.storage.corpus import CorpusManager


class DocumentService:
    def __init__(self, db: AsyncSession, corpus_manager: Optional[CorpusManager] = None):
        self._db = db
        self._corpus_manager = corpus_manager
        self._seeded = False

    async def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        count_result = await self._db.execute(select(func.count(CorpusDocument.ruo_id)))
        count = count_result.scalar() or 0
        if count > 0:
            self._seeded = True
            return
        if self._corpus_manager is None:
            self._seeded = True
            return
        if not hasattr(self._corpus_manager, "store") or self._corpus_manager.store is None:
            self._seeded = True
            return
        docs = self._corpus_manager.get_documents()
        if not docs:
            self._seeded = True
            return
        records = []
        for doc in docs:
            author_names = [a.full_name for a in doc.header.authors or []]
            year = None
            if doc.header.publication_date:
                try:
                    year = int(doc.header.publication_date[:4])
                except (ValueError, TypeError):
                    pass
            stages = doc.meta.pipeline_stages or []
            final_status = stages[-1] if stages else "success"
            entity_count = len(doc.entities or [])
            source = doc.header.venue if doc.header.venue else None
            records.append(CorpusDocument(
                ruo_id=doc.meta.ruo_id,
                title=doc.header.title,
                authors_json=author_names,
                year=year,
                status=final_status,
                entity_count=entity_count,
                source=source,
            ))
        self._db.add_all(records)
        await self._db.commit()
        self._seeded = True

    async def list_documents(
        self,
        page_index: int = 0,
        page_size: int = 10,
        search_query: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_direction: str = "desc",
    ) -> PaginatedDocumentsResponse:
        await self._ensure_seeded()
        query = select(CorpusDocument)
        count_query = select(func.count(CorpusDocument.ruo_id))

        if search_query:
            search_lower = f"%{search_query.lower()}%"
            filter_cond = or_(
                func.lower(CorpusDocument.title).like(search_lower),
            )
            query = query.where(filter_cond)
            count_query = count_query.where(filter_cond)

        reverse = sort_direction.lower() != "asc"
        if sort_by == "title":
            order_col = CorpusDocument.title
        elif sort_by == "year":
            order_col = CorpusDocument.year
        elif sort_by == "status":
            order_col = CorpusDocument.status
        elif sort_by == "entity_count":
            order_col = CorpusDocument.entity_count
        else:
            order_col = CorpusDocument.created_at
        order_func = desc if reverse else asc
        query = query.order_by(order_func(order_col), CorpusDocument.ruo_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        offset = page_index * page_size
        query = query.offset(offset).limit(page_size)
        result = await self._db.execute(query)
        rows = result.scalars().all()

        items = []
        for row in rows:
            authors = row.authors_json if isinstance(row.authors_json, list) else []
            items.append(DocumentListItem(
                ruo_id=row.ruo_id,
                title=row.title,
                authors=authors,
                year=row.year,
                status=row.status,
                entity_count=row.entity_count,
                source=row.source,
            ))

        return PaginatedDocumentsResponse(data=items, total=total)

    async def get_document(self, ruo_id: str) -> Optional[DocumentDetail]:
        await self._ensure_seeded()
        result = await self._db.execute(
            select(CorpusDocument).where(CorpusDocument.ruo_id == ruo_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        authors = row.authors_json if isinstance(row.authors_json, list) else []
        return DocumentDetail(
            ruo_id=row.ruo_id,
            title=row.title,
            authors=authors,
            year=row.year,
            status=row.status,
            entity_count=row.entity_count,
            source=row.source,
        )

    async def get_full_document(self, ruo_id: str):
        if self._corpus_manager is None:
            return None
        if not hasattr(self._corpus_manager, "store") or self._corpus_manager.store is None:
            return None
        try:
            return self._corpus_manager.store.get(ruo_id)
        except Exception:
            return None
