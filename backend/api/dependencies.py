from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Any
from .exceptions import AuthException
from .auth.security import decode_access_token

# Import M5 and M6 Components
from researchmind.query.parser import QueryParser
from researchmind.query.planner import QueryPlanner
from researchmind.query.router import StepDispatcher
from researchmind.query.engine import QueryEngine
from researchmind.synthesis.orchestrator import ReviewOrchestrator
from researchmind.synthesis.traceability import TraceabilityVerifier

# In a real app these would be proper classes with their own dependencies,
# but for Phase 2 we provide basic empty/default instances where appropriate.
class DummyCorpusManager:
    pass

class DummyGraph:
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

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Validate the JWT token and return the payload.
    In Phase 1, there is no database. We simply parse the token and return it.
    """
    payload = decode_access_token(token)
    if not payload:
        raise AuthException("Could not validate credentials")
    
    username: str = payload.get("sub")
    if username is None:
        raise AuthException("Token payload invalid")
    
    return {"username": username}

def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    # Future placeholder for checking if user is banned/disabled in DB
    return current_user

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
