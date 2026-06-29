from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission, require_identity_user
from app.db.session import get_db_session
from app.schemas.quiz import (
    EducatorQuizDraftAcceptRequest,
    EducatorQuizDraftGenerateRequest,
    EducatorQuizDraftPreviewResponse,
    QuizAttemptHistoryResponse,
    QuizAttemptResultResponse,
    QuizAttemptStartResponse,
    QuizAttemptSubmitRequest,
    QuizAuthoringResponse,
    QuizQuestionPageResponse,
    QuizQuestionWriteRequest,
    QuizPublishRequest,
    QuizUpsertRequest,
)
from app.schemas.quiz_generation import GeneratedQuizAttemptStartRequest
from app.services.quiz_service import QuizService
from platform_common.permissions.codes import MODULE_PUBLISH, MODULE_UPDATE


router = APIRouter(prefix="/courses/{course_uuid}/modules/{module_uuid}/quiz", tags=["quiz"])


@router.put(
    "",
    summary="Create Or Upsert Quiz [Educator Owner/Admin]",
    description="Creates the module quiz or incrementally upserts quiz metadata and referenced questions while keeping the quiz in draft.",
    response_model=QuizAuthoringResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def upsert_quiz(
    course_uuid: str,
    module_uuid: str,
    payload: QuizUpsertRequest,
    include_questions: bool = True,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> QuizAuthoringResponse:
    return QuizService(session).upsert_quiz(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
        include_questions=include_questions,
    )


@router.get(
    "/management",
    summary="Get Quiz Authoring Detail [Educator Owner/Admin]",
    description="Returns the current quiz authoring detail for a module.",
    response_model=QuizAuthoringResponse,
    response_model_exclude_none=True,
)
def get_quiz_authoring_detail(
    course_uuid: str,
    module_uuid: str,
    include_questions: bool = True,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> QuizAuthoringResponse:
    return QuizService(session).get_quiz_authoring_detail(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
        include_questions=include_questions,
    )


@router.get(
    "/management/questions",
    summary="List Quiz Authoring Questions [Educator Owner/Admin]",
    description="Returns one page of quiz question pool entries for management views.",
    response_model=QuizQuestionPageResponse,
)
def list_quiz_authoring_questions(
    course_uuid: str,
    module_uuid: str,
    page: int = 1,
    page_size: int = 20,
    query: str | None = None,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> QuizQuestionPageResponse:
    return QuizService(session).list_quiz_authoring_questions(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
        page=page,
        page_size=page_size,
        query=query,
    )


@router.post(
    "/management/ai-draft",
    summary="Preview AI Quiz Draft [Educator Owner/Admin]",
    description="Generates an editable AI quiz draft preview from module materials without saving it to the quiz question pool.",
    response_model=EducatorQuizDraftPreviewResponse,
    response_model_exclude_none=True,
)
def generate_ai_quiz_draft(
    course_uuid: str,
    module_uuid: str,
    payload: EducatorQuizDraftGenerateRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> EducatorQuizDraftPreviewResponse:
    return QuizService(session).generate_educator_ai_draft(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/management/ai-draft/accept",
    summary="Accept AI Quiz Draft [Educator Owner/Admin]",
    description="Persists a reviewed AI quiz draft preview as the module's unpublished quiz authoring draft.",
    response_model=QuizAuthoringResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def accept_ai_quiz_draft(
    course_uuid: str,
    module_uuid: str,
    payload: EducatorQuizDraftAcceptRequest,
    include_questions: bool = True,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> QuizAuthoringResponse:
    return QuizService(session).accept_educator_ai_draft(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
        include_questions=include_questions,
    )


@router.post(
    "/publish",
    summary="Publish Quiz [Educator Owner/Admin]",
    description="Changes quiz status after validating that the question bank is publishable.",
    response_model=QuizAuthoringResponse,
    response_model_exclude_none=True,
)
def publish_quiz(
    course_uuid: str,
    module_uuid: str,
    payload: QuizPublishRequest,
    include_questions: bool = True,
    current_user: dict = Depends(require_identity_permission(MODULE_PUBLISH)),
    session: Session = Depends(get_db_session),
) -> QuizAuthoringResponse:
    return QuizService(session).publish_quiz(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
        include_questions=include_questions,
    )


@router.post(
    "/questions",
    summary="Add Quiz Question [Educator Owner/Admin]",
    description="Adds a single question to the module quiz and saves the quiz back to draft.",
    response_model=QuizAuthoringResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_quiz_question(
    course_uuid: str,
    module_uuid: str,
    payload: QuizQuestionWriteRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> QuizAuthoringResponse:
    return QuizService(session).create_question(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.patch(
    "/questions/{question_uuid}",
    summary="Update Quiz Question [Educator Owner/Admin]",
    description="Updates a single question or archives it and creates a replacement when historical attempts already exist.",
    response_model=QuizAuthoringResponse,
    response_model_exclude_none=True,
)
def update_quiz_question(
    course_uuid: str,
    module_uuid: str,
    question_uuid: str,
    payload: QuizQuestionWriteRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> QuizAuthoringResponse:
    return QuizService(session).update_question(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        question_uuid=question_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/active-session",
    summary="Get Active Quiz Session [Learner]",
    description="Returns the learner's in-progress quiz session if one exists, so it can be restored after a page refresh. Returns 204 when no active session exists.",
    response_model=QuizAttemptStartResponse,
    response_model_exclude_none=True,
)
def get_active_quiz_session(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> QuizAttemptStartResponse | Response:
    result = QuizService(session).get_active_attempt_session(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )
    if result is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return result


@router.post(
    "/attempt-sessions",
    summary="Start Quiz Attempt [Learner]",
    description="Creates a server-side quiz attempt session with randomized questions and timing snapshots.",
    response_model=QuizAttemptStartResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def start_quiz_attempt(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> QuizAttemptStartResponse:
    return QuizService(session).start_attempt(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )


@router.post(
    "/generated-attempt-sessions",
    summary="Start Generated Quiz Attempt [Learner]",
    description="Creates a server-side quiz attempt session using an explicit generated question set instead of the default random selection.",
    response_model=QuizAttemptStartResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def start_generated_quiz_attempt(
    course_uuid: str,
    module_uuid: str,
    payload: GeneratedQuizAttemptStartRequest,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> QuizAttemptStartResponse:
    return QuizService(session).start_generated_attempt(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/attempt-sessions/{attempt_session_token}/submit",
    summary="Submit Quiz Attempt [Learner]",
    description="Submits answers for a quiz attempt session, auto-grades them, and returns immediate feedback.",
    response_model=QuizAttemptResultResponse,
    response_model_exclude_none=True,
)
def submit_quiz_attempt(
    course_uuid: str,
    module_uuid: str,
    attempt_session_token: str,
    payload: QuizAttemptSubmitRequest,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> QuizAttemptResultResponse:
    return QuizService(session).submit_attempt(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        attempt_session_token=attempt_session_token,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/attempts",
    summary="List My Quiz Attempts [Learner]",
    description="Returns the current learner's attempt history for the module quiz.",
    response_model=QuizAttemptHistoryResponse,
    response_model_exclude_none=True,
)
def list_quiz_attempts(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> QuizAttemptHistoryResponse:
    return QuizService(session).list_attempt_history(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )


@router.get(
    "/attempts/{quiz_attempt_uuid}",
    summary="Get My Quiz Attempt Detail [Learner]",
    description="Returns the detailed graded result for one of the current learner's historical quiz attempts.",
    response_model=QuizAttemptResultResponse,
    response_model_exclude_none=True,
)
def get_quiz_attempt_detail(
    course_uuid: str,
    module_uuid: str,
    quiz_attempt_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> QuizAttemptResultResponse:
    return QuizService(session).get_attempt_detail(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        quiz_attempt_uuid=quiz_attempt_uuid,
        current_user=current_user,
    )
