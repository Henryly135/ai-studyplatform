from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from app.core.uuid_codec import decode_course_uuid, decode_module_uuid
from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import Course, CourseStatus
from app.models.modules import Module, ModuleStatus
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_repository import ModuleRepository
from app.services.module_unlocking_service import ModuleUnlockingService
from platform_common.errors import http_error


class AIContextAccessService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.unlocking = ModuleUnlockingService(session)

    def ensure_chat_context_access(
        self,
        *,
        course_uuid: str,
        module_uuid: str | None,
        user_id: int,
        identity: str,
    ) -> None:
        course = self._get_course(course_uuid)
        normalized_identity = identity.strip()

        if normalized_identity == "Admin":
            if module_uuid is not None:
                self._get_course_module(course=course, module_uuid=module_uuid)
            return

        if normalized_identity == "Educator":
            if course.educator_id != user_id:
                raise http_error(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="AI_CONTEXT_FORBIDDEN",
                    message="AI chat context is not available for this course",
                )
            if module_uuid is not None:
                self._get_course_module(course=course, module_uuid=module_uuid)
            return

        if normalized_identity != "Learner":
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="AI_CONTEXT_FORBIDDEN",
                message="AI chat context is not available for this identity",
            )

        if module_uuid is None:
            raise http_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="AI_MODULE_CONTEXT_REQUIRED",
                message="Learner AI chat requires a module context",
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
        if enrollment is None or enrollment.enrollment_status not in {EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED}:
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="COURSE_ENROLLMENT_REQUIRED",
                message="AI chat context requires an active course enrollment",
            )

        module = self._get_course_module(course=course, module_uuid=module_uuid)
        if module.status != ModuleStatus.PUBLISHED:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MODULE_NOT_AVAILABLE",
                message="Module is not available",
            )
        if module.visible_to_class_id:
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="AI_CONTEXT_FORBIDDEN",
                message="AI chat context is not available for this module",
            )

        self.unlocking.ensure_module_unlocked(
            module_id=module.module_id,
            learner_id=user_id,
            resource_name="AI chat context",
        )

    def _get_course(self, course_uuid: str) -> Course:
        course = self.courses.get_by_id(decode_course_uuid(course_uuid))
        if course is None:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message="Course not found",
            )
        return course

    def _get_course_module(self, *, course: Course, module_uuid: str) -> Module:
        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        if learning_path is None:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LEARNING_PATH_NOT_FOUND",
                message="Learning path not found",
            )

        module = self.modules.get_by_id(decode_module_uuid(module_uuid))
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MODULE_NOT_FOUND",
                message="Module not found",
            )
        return module
