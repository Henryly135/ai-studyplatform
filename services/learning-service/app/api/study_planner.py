from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_user
from app.db.session import get_db_session
from app.schemas.study_planner import StudyPlanCreateRequest, StudyPlanResponse, StudyPlanUpdateRequest
from app.services.study_planner_service import StudyPlannerService


router = APIRouter(prefix="/study-plans", tags=["study-planner"])


@router.post(
    "",
    summary="Create Study Plan [Learner]",
    response_model=StudyPlanResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_study_plan(
    payload: StudyPlanCreateRequest,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> StudyPlanResponse:
    return StudyPlannerService(session).create_plan(payload=payload, current_user=current_user)


@router.get(
    "",
    summary="List Study Plans [Learner]",
    response_model=list[StudyPlanResponse],
    response_model_exclude_none=True,
)
def list_study_plans(
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> list[StudyPlanResponse]:
    return StudyPlannerService(session).list_plans(current_user=current_user)


@router.get(
    "/{plan_uuid}",
    summary="Get Study Plan [Learner]",
    response_model=StudyPlanResponse,
    response_model_exclude_none=True,
)
def get_study_plan(
    plan_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> StudyPlanResponse:
    return StudyPlannerService(session).get_plan(plan_uuid=plan_uuid, current_user=current_user)


@router.patch(
    "/{plan_uuid}",
    summary="Update Study Plan [Learner]",
    response_model=StudyPlanResponse,
    response_model_exclude_none=True,
)
def update_study_plan(
    plan_uuid: str,
    payload: StudyPlanUpdateRequest,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> StudyPlanResponse:
    return StudyPlannerService(session).update_plan(
        plan_uuid=plan_uuid,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/{plan_uuid}/regenerate",
    summary="Regenerate Study Plan [Learner]",
    response_model=StudyPlanResponse,
    response_model_exclude_none=True,
)
def regenerate_study_plan(
    plan_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> StudyPlanResponse:
    return StudyPlannerService(session).regenerate_plan(plan_uuid=plan_uuid, current_user=current_user)
