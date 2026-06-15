from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from researchmind.storage.corpus import CorpusManager
from backend.api.dependencies import get_corpus_manager
from backend.api.schemas.documents import PaginatedDocumentsResponse

router = APIRouter()

@router.get("", response_model=PaginatedDocumentsResponse)
async def get_documents(
    pageIndex: int = 0,
    pageSize: int = 10,
    corpus: CorpusManager = Depends(get_corpus_manager)
):
    # If the _docs in mock_data failed to load, fallback safely.
    if not hasattr(corpus, "store") or corpus.store() is None:
        return PaginatedDocumentsResponse(data=[], total=0)

    # Note: store().list() is a generic signature; assuming we just list all to memory to paginate.
    try:
        all_docs = []
        for d in corpus.store().list_all():
            all_docs.append(d)
        
        # Sort descending by updated_at or created_at
        all_docs.sort(key=lambda x: x.meta.created_at, reverse=True)
        
        start = pageIndex * pageSize
        end = start + pageSize
        page_docs = all_docs[start:end]
        
        # FastAPI will automatically serialize the Pydantic models (RUODocument)
        return PaginatedDocumentsResponse(
            data=page_docs,
            total=len(all_docs)
        )
    except Exception:
        # Fallback if list_all() isn't implemented or throws
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
