from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.quiz_generation import (
    GeneratedQuizAttemptInternalStartRequest,
    QuizGenerationAuthoringAccessRequest,
    QuizGenerationAuthoringAccessResponse,
    GeneratedQuizQuestionsCreateRequest,
    GeneratedQuizQuestionsCreateResponse,
    QuizGenerationLearnerAccessRequest,
    QuizGenerationLearnerAccessResponse,
    QuizGenerationContextRequest,
    QuizGenerationContextResponse,
)
from app.schemas.quiz import QuizAttemptStartResponse
from app.services.quiz_service import QuizService


router = APIRouter(prefix="/internal/quiz-generation", tags=["internal-quiz-generation"])


@router.post("/learner-access", response_model=QuizGenerationLearnerAccessResponse)
def check_quiz_generation_learner_access(
    payload: QuizGenerationLearnerAccessRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> QuizGenerationLearnerAccessResponse:
    QuizService(session).ensure_learner_quiz_access(
        course_uuid=payload.courseUuid,
        module_uuid=payload.moduleUuid,
        learner_id=payload.learnerId,
    )
    return QuizGenerationLearnerAccessResponse(allowed=True)


@router.post("/authoring-access", response_model=QuizGenerationAuthoringAccessResponse)
def check_quiz_generation_authoring_access(
    payload: QuizGenerationAuthoringAccessRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> QuizGenerationAuthoringAccessResponse:
    QuizService(session).ensure_authoring_quiz_access(
        course_uuid=payload.courseUuid,
        module_uuid=payload.moduleUuid,
        actor_id=payload.actorId,
        actor_identity=payload.actorIdentity,
    )
    return QuizGenerationAuthoringAccessResponse(allowed=True)


@router.post("/context", response_model=QuizGenerationContextResponse)
def get_quiz_generation_context(
    payload: QuizGenerationContextRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> QuizGenerationContextResponse:
    return QuizService(session).get_quiz_generation_context(
        course_uuid=payload.courseUuid,
        module_uuid=payload.moduleUuid,
    )


@router.post("/questions/batch-create", response_model=GeneratedQuizQuestionsCreateResponse)
def batch_create_generated_questions(
    payload: GeneratedQuizQuestionsCreateRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> GeneratedQuizQuestionsCreateResponse:
    return QuizService(session).batch_create_generated_questions(
        course_uuid=payload.courseUuid,
        module_uuid=payload.moduleUuid,
        purpose=payload.purpose,
        questions=payload.questions,
    )


@router.post("/generated-attempt-sessions", response_model=QuizAttemptStartResponse)
def start_generated_quiz_attempt_internal(
    payload: GeneratedQuizAttemptInternalStartRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> QuizAttemptStartResponse:
    return QuizService(session).start_generated_attempt_internal(
        course_uuid=payload.courseUuid,
        module_uuid=payload.moduleUuid,
        learner_id=payload.learnerId,
        question_uuids=payload.questionUuids,
    )
