from fastapi import APIRouter, Depends, HTTPException
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
)
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
    engine: QueryEngine = Depends(get_query_engine)
):
    try:
        from datetime import datetime, timezone
        # Reconstruct the ResearchQuery object required by engine.execute
        query = ResearchQuery.model_construct(
            query_id=request.query_id, 
            raw_query=request.raw_query,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        
        # execution returns a tuple of (parsed, plan, route, evidence, answer)
        parsed, plan, route, evidence, answer = engine.execute(query)
        
        return {
            "parsed_query": parsed.model_dump(),
            "execution_plan": plan.model_dump(),
            "step_route": route.model_dump(),
            "evidence": [e.model_dump() for e in evidence],
            "answer": answer.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
