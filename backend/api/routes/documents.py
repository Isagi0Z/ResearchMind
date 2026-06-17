from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from researchmind.storage.corpus import CorpusManager
from backend.api.dependencies import get_corpus_manager
from backend.api.schemas.documents import PaginatedDocumentsResponse

router = APIRouter()

@router.get("", response_model=PaginatedDocumentsResponse)
async def get_documents(
    pageIndex: int = 0,
    pageSize: int = 10,
    searchQuery: Optional[str] = Query(None, alias="searchQuery"),
    sortBy: Optional[str] = Query(None, alias="sortBy"),
    sortDirection: Optional[str] = Query("desc", alias="sortDirection"),
    corpus: CorpusManager = Depends(get_corpus_manager)
):
    if not hasattr(corpus, "store") or corpus.store() is None:
        return PaginatedDocumentsResponse(data=[], total=0)

    try:
        all_docs = []
        for d in corpus.store().list_all():
            all_docs.append(d)

        # Apply search filter
        if searchQuery:
            search_lower = searchQuery.lower()
            filtered = []
            for d in all_docs:
                title_match = search_lower in d.header.title.lower()
                author_match = any(search_lower in a.full_name.lower() for a in d.header.authors)
                if title_match or author_match:
                    filtered.append(d)
            all_docs = filtered

        # Sort
        reverse = sortDirection != "asc"
        if sortBy == "title":
            all_docs.sort(key=lambda x: x.header.title.lower(), reverse=reverse)
        elif sortBy == "year":
            all_docs.sort(key=lambda x: x.header.publication_date or "", reverse=reverse)
        else:
            all_docs.sort(key=lambda x: x.meta.created_at, reverse=reverse)

        start = pageIndex * pageSize
        end = start + pageSize
        page_docs = all_docs[start:end]

        return PaginatedDocumentsResponse(
            data=page_docs,
            total=len(all_docs)
        )
    except Exception:
        return PaginatedDocumentsResponse(data=[], total=0)

@router.get("/{id}")
async def get_document(id: str, corpus: CorpusManager = Depends(get_corpus_manager)):
    if not hasattr(corpus, "store") or corpus.store() is None:
        raise HTTPException(status_code=404, detail="Document not found")
        
    try:
        doc = corpus.store().get(id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")
