from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from researchmind.query.parser import QueryParser
from researchmind.query.planner import QueryPlanner
from researchmind.query.router import StepDispatcher
from researchmind.query.engine import QueryEngine
from researchmind.query.models import ParsedQuery, ResearchQuery, ExecutionPlan

from backend.api.dependencies import (
    get_query_parser,
    get_query_planner,
    get_step_dispatcher,
    get_query_engine,
    get_current_user_optional
)
from backend.db.session import get_db
from backend.db.models.query import Query
from backend.db.models.user import User
from backend.api.schemas.query import ParseRequest, AnswerRequest

router = APIRouter()

@router.post("/parse")
async def parse_query(
    request: ParseRequest,
    parser: QueryParser = Depends(get_query_parser)
):
    try:
        parsed = parser.parse(request.raw_query)
        return {"parsed_query": parsed.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/plan")
async def plan_query(
    request: ParsedQuery,
    planner: QueryPlanner = Depends(get_query_planner)
):
    try:
        plan = planner.create_plan(request)
        return {"execution_plan": plan.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/route")
async def route_query(
    request: ExecutionPlan,
    dispatcher: StepDispatcher = Depends(get_step_dispatcher)
):
    try:
        routes = dispatcher.route_plan(request)
        return {"step_routes": [r.model_dump() for r in routes]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/answer")
async def answer_query(
    request: AnswerRequest,
    engine: QueryEngine = Depends(get_query_engine),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    try:
        from datetime import datetime, timezone
        query = ResearchQuery.model_construct(
            query_id=request.query_id, 
            raw_query=request.raw_query,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        
        parsed, plan, route, evidence, answer = engine.execute(query)
        
        result_dump = {
            "parsed_query": parsed.model_dump(),
            "execution_plan": plan.model_dump(),
            "step_route": route.model_dump(),
            "evidence": [e.model_dump() for e in evidence],
            "answer": answer.model_dump(),
        }

        # Persist if user is logged in
        if current_user:
            db_query = Query(
                user_id=current_user.id,
                raw_query=request.raw_query,
                query_type=parsed.query_type if parsed else "UNKNOWN",
                result=result_dump
            )
            db.add(db_query)
            await db.commit()

        return result_dump
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
