from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission, require_identity_user
from app.db.session import get_db_session
from app.schemas.short_answer import (
    ShortAnswerAssessmentResponse,
    ShortAnswerAssessmentUpsertRequest,
    ShortAnswerLearnerAssessmentResponse,
    ShortAnswerSubmissionCreateRequest,
    ShortAnswerSubmissionResponse,
    ShortAnswerSubmissionReviewRequest,
)
from app.services.short_answer_service import ShortAnswerService
from platform_common.permissions.codes import MODULE_UPDATE, QUIZ_ATTEMPT


router = APIRouter(prefix="/courses/{course_uuid}/modules/{module_uuid}/short-answer", tags=["short-answer"])


@router.put(
    "/management",
    summary="Create Or Update Short-Answer Assessment [Educator Owner/Admin]",
    response_model=ShortAnswerAssessmentResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def upsert_short_answer_assessment(
    course_uuid: str,
    module_uuid: str,
    payload: ShortAnswerAssessmentUpsertRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ShortAnswerAssessmentResponse:
    return ShortAnswerService(session).upsert_assessment(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/management",
    summary="Get Short-Answer Assessment [Educator Owner/Admin]",
    response_model=ShortAnswerAssessmentResponse,
    response_model_exclude_none=True,
)
def get_short_answer_assessment_management(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ShortAnswerAssessmentResponse:
    return ShortAnswerService(session).get_management_assessment(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )


@router.get(
    "/management/submissions",
    summary="List Short-Answer Submissions [Educator Owner/Admin]",
    response_model=list[ShortAnswerSubmissionResponse],
    response_model_exclude_none=True,
)
def list_short_answer_submissions(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> list[ShortAnswerSubmissionResponse]:
    return ShortAnswerService(session).list_submissions(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )


@router.patch(
    "/management/submissions/{submission_uuid}/review",
    summary="Review Short-Answer Submission [Educator Owner/Admin]",
    response_model=ShortAnswerSubmissionResponse,
    response_model_exclude_none=True,
)
def review_short_answer_submission(
    course_uuid: str,
    module_uuid: str,
    submission_uuid: str,
    payload: ShortAnswerSubmissionReviewRequest,
    current_user: dict = Depends(require_identity_permission(MODULE_UPDATE)),
    session: Session = Depends(get_db_session),
) -> ShortAnswerSubmissionResponse:
    return ShortAnswerService(session).review_submission(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        submission_uuid=submission_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "",
    summary="Get Short-Answer Assessment [Learner]",
    response_model=ShortAnswerLearnerAssessmentResponse,
    response_model_exclude_none=True,
)
def get_short_answer_assessment(
    course_uuid: str,
    module_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> ShortAnswerLearnerAssessmentResponse:
    return ShortAnswerService(session).get_learner_assessment(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        current_user=current_user,
    )


@router.post(
    "/submissions",
    summary="Submit Short-Answer Assessment [Learner]",
    response_model=ShortAnswerSubmissionResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def submit_short_answer(
    course_uuid: str,
    module_uuid: str,
    payload: ShortAnswerSubmissionCreateRequest,
    current_user: dict = Depends(require_identity_permission(QUIZ_ATTEMPT)),
    session: Session = Depends(get_db_session),
) -> ShortAnswerSubmissionResponse:
    return ShortAnswerService(session).submit_answer(
        course_uuid=course_uuid,
        module_uuid=module_uuid,
        payload=payload,
        current_user=current_user,
    )
