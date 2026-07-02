from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from app.core.uuid_codec import decode_course_uuid
from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import CourseStatus
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_repository import CourseRepository
from platform_common.errors import http_error


class CourseSpaceAccessService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)

    def ensure_forum_access(
        self,
        *,
        course_uuid: str,
        user_id: int,
        identity: str,
    ) -> None:
        course = self.courses.get_by_id(decode_course_uuid(course_uuid))
        if course is None:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message="Course not found",
            )

        normalized_identity = identity.strip()
        if normalized_identity == "Admin":
            return
        if normalized_identity == "Educator" and course.educator_id == user_id:
            return
        if normalized_identity != "Learner":
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="COURSE_FORUM_FORBIDDEN",
                message="Course forum is not available for this identity",
            )

        if course.status != CourseStatus.PUBLISHED:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_AVAILABLE",
                message="Course is not available",
            )

        enrollment = self.enrollments.get_by_course_and_learner(
            course_id=course.course_id,
            learner_id=user_id,
        )
        if enrollment is None or enrollment.enrollment_status not in {
            EnrollmentStatus.ACTIVE,
            EnrollmentStatus.COMPLETED,
        }:
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="COURSE_ENROLLMENT_REQUIRED",
                message="Course forum requires an active course enrollment",
            )
