from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from .exceptions import AuthException
from .auth.security import decode_access_token
from backend.api.auth.security import JWT_ISSUER
from backend.api.auth.cookies import ACCESS_TOKEN_COOKIE
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.session import get_db
from backend.db.models.user import User
import uuid

# Import M5 and M6 Components
from researchmind.query.parser import QueryParser
from researchmind.query.planner import QueryPlanner
from researchmind.query.router import StepDispatcher
from researchmind.query.engine import QueryEngine
from researchmind.synthesis.orchestrator import ReviewOrchestrator
from researchmind.synthesis.traceability import TraceabilityVerifier
from researchmind.storage.corpus import CorpusManager
from backend.api.mock_data import generate_mock_documents

class DummyGraph:
    pass

try:
    _docs = generate_mock_documents()
    _corpus_manager = CorpusManager.from_documents(_docs, "corpus-1")
except Exception as e:
    import logging
    logging.warning(f"Failed to initialize mock CorpusManager: {e}")
    class DummyCorpusManager:
        pass
    _corpus_manager = DummyCorpusManager()

_graph = DummyGraph()

_query_parser = QueryParser(corpus=_corpus_manager)
_query_planner = QueryPlanner()
_step_dispatcher = StepDispatcher()
_query_engine = QueryEngine(
    parser=_query_parser,
    planner=_query_planner,
    dispatcher=_step_dispatcher
)
_review_orchestrator = ReviewOrchestrator(
    corpus_manager=_corpus_manager,
    graph=_graph
)
_traceability_verifier = TraceabilityVerifier()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

async def get_current_user_optional(
    request: Request = None,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    if not token and request:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    if payload.get("iss") != JWT_ISSUER:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return None
        
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    return user

async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    if not user:
        raise AuthException("Could not validate credentials")
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise AuthException("Inactive user")
    return current_user

def require_role(required_role: str):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role:
            raise AuthException(f"Missing required role: {required_role}")
        return current_user
    return role_checker

def get_query_parser() -> QueryParser:
    return _query_parser

def get_query_planner() -> QueryPlanner:
    return _query_planner

def get_step_dispatcher() -> StepDispatcher:
    return _step_dispatcher

def get_query_engine() -> QueryEngine:
    return _query_engine

def get_review_orchestrator() -> ReviewOrchestrator:
    return _review_orchestrator

def get_traceability_verifier() -> TraceabilityVerifier:
    return _traceability_verifier

def get_corpus_manager():
    return _corpus_manager
