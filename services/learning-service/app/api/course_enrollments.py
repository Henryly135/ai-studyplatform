from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission, require_identity_user
from app.db.session import get_db_session
from app.schemas.course import (
    CourseEnrollmentLearnerResponse,
    CourseEnrollmentResponse,
    CourseEnrollmentStatusUpdateRequest,
    CourseSummaryResponse,
)
from app.schemas.learner_progress import LearnerProgressOverviewResponse
from app.services.course_catalog_service import CourseCatalogService
from app.services.course_enrollment_service import CourseEnrollmentService, CourseEnrollmentServiceError
from app.services.learner_progress_service import LearnerProgressService
from platform_common.permissions.codes import COURSE_ENROL, COURSE_ENROLLMENT_MANAGE


router = APIRouter(prefix="/courses", tags=["course-enrollments"])


@router.get(
    "/{course_uuid}/enrolments",
    summary="List Course Enrollments [Educator Owner/Admin]",
    description="Returns the current non-dropped learner enrollments for a course.",
    response_model=list[CourseEnrollmentLearnerResponse],
    response_model_exclude_none=True,
)
def list_course_enrollments(
    course_uuid: str,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROLLMENT_MANAGE)),
    session: Session = Depends(get_db_session),
) -> list[CourseEnrollmentLearnerResponse]:
    try:
        return CourseEnrollmentService(session).list_course_enrollments(course_uuid=course_uuid, current_user=current_user)
    except CourseEnrollmentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/{course_uuid}/enrolments",
    summary="Enrol Course [Learner]",
    description="Enrols the current learner into a published course.",
    response_model=CourseEnrollmentResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def enrol_course(
    course_uuid: str,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROL)),
    session: Session = Depends(get_db_session),
) -> CourseEnrollmentResponse:
    try:
        return CourseEnrollmentService(session).enrol_course(course_uuid=course_uuid, current_user=current_user)
    except CourseEnrollmentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.delete(
    "/{course_uuid}/enrolments/me",
    summary="Drop My Course Enrollment [Learner]",
    description="Drops the current learner's own enrollment for a course.",
    response_model=CourseEnrollmentResponse,
    response_model_exclude_none=True,
)
def drop_my_course_enrollment(
    course_uuid: str,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROL)),
    session: Session = Depends(get_db_session),
) -> CourseEnrollmentResponse:
    try:
        return CourseEnrollmentService(session).drop_own_enrollment(course_uuid=course_uuid, current_user=current_user)
    except CourseEnrollmentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.patch(
    "/{course_uuid}/enrolments/{learner_uuid}/status",
    summary="Update Course Enrollment Status [Educator Owner/Admin]",
    description="Updates a learner enrollment status for course management.",
    response_model=CourseEnrollmentResponse,
    response_model_exclude_none=True,
)
def update_course_enrollment_status(
    course_uuid: str,
    learner_uuid: str,
    payload: CourseEnrollmentStatusUpdateRequest,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROLLMENT_MANAGE)),
    session: Session = Depends(get_db_session),
) -> CourseEnrollmentResponse:
    try:
        return CourseEnrollmentService(session).update_enrollment_status(
            course_uuid=course_uuid,
            learner_uuid=learner_uuid,
            enrollment_status=payload.enrollmentStatus,
            current_user=current_user,
            reason=payload.reason,
        )
    except CourseEnrollmentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/me/enrolled",
    summary="List My Enrolled Courses [Learner]",
    description="Returns the current learner's enrolled published courses.",
    response_model=list[CourseSummaryResponse],
    response_model_exclude_none=True,
)
def list_my_enrolled_courses(
    search: str | None = Query(default=None),
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
):
    return CourseCatalogService(session).list_enrolled_courses(current_user=current_user, search=search)


@router.get(
    "/me/progress-overview",
    summary="Get My Learning Progress Overview [Learner]",
    description="Returns the current learner's course progress, quiz score summary, and recent activity in one aggregate response.",
    response_model=LearnerProgressOverviewResponse,
    response_model_exclude_none=True,
)
def get_my_progress_overview(
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> LearnerProgressOverviewResponse:
    return LearnerProgressService(session).get_overview(current_user=current_user)
