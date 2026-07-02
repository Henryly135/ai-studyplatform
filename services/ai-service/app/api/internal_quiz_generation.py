from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_internal_request
from app.db.session import get_db_session
from app.services.orchestration.langgraph.checkpointer import build_graph_config, get_langgraph_checkpointer
from app.services.orchestration.langgraph.quiz_generation_graph import QuizGenerationGraphRunner
from app.services.workflows.quiz_generation.schemas import QuizGenerationRequest, QuizGenerationRunResponse


router = APIRouter(prefix="/internal/quiz-generation", tags=["internal-quiz-generation"])


@router.post("/run", response_model=QuizGenerationRunResponse)
def run_quiz_generation(
    payload: QuizGenerationRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> QuizGenerationRunResponse:
    thread_id = f"quiz-generation:{payload.educatorId}:{payload.courseUuid}:{payload.moduleUuid}:internal"
    config = build_graph_config(thread_id=thread_id, checkpoint_ns="quiz_generation")
    return QuizGenerationGraphRunner(
        session,
        checkpointer=get_langgraph_checkpointer(),
    ).run(payload=payload, config=config)
