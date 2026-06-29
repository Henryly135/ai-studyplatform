from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_internal_request
from app.db.session import get_db_session
from app.services.orchestration.langgraph.checkpointer import build_graph_config, get_langgraph_checkpointer
from app.services.orchestration.langgraph.quiz_generation_graph import QuizGenerationGraphRunner
from app.services.workflows.quiz_generation.schemas import (
    EducatorQuizDraftGenerationRequest,
    EducatorQuizDraftGenerationResponse,
    QuizGenerationRequest,
    QuizGenerationRunResponse,
)
from app.services.workflows.quiz_generation.services.educator_draft_service import EducatorQuizDraftGenerationService


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


@router.post("/educator-draft", response_model=EducatorQuizDraftGenerationResponse)
def generate_educator_quiz_draft(
    payload: EducatorQuizDraftGenerationRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> EducatorQuizDraftGenerationResponse:
    return EducatorQuizDraftGenerationService(session).generate_draft(payload)
