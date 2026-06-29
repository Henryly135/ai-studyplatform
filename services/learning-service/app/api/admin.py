from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission
from app.db.session import get_db_session
from app.schemas.course import AdminCourseEnrollmentManageRequest, CourseEnrollmentResponse
from app.services.course_enrollment_service import CourseEnrollmentService, CourseEnrollmentServiceError
from platform_common.permissions.codes import COURSE_ENROLLMENT_MANAGE

router = APIRouter(prefix="/admin", tags=["admin"])


@router.put("/courses/{course_uuid}/enrolments/{learner_uuid}", response_model=CourseEnrollmentResponse)
def admin_manage_course_enrollment(
    course_uuid: str,
    learner_uuid: str,
    payload: AdminCourseEnrollmentManageRequest,
    current_user: dict = Depends(require_identity_permission(COURSE_ENROLLMENT_MANAGE)),
    session: Session = Depends(get_db_session),
) -> CourseEnrollmentResponse:
    try:
        return CourseEnrollmentService(session).admin_manage_enrollment(
            course_uuid=course_uuid,
            learner_uuid=learner_uuid,
            enrollment_status=payload.enrollmentStatus,
            current_user=current_user,
            reason=payload.reason,
        )
    except CourseEnrollmentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
