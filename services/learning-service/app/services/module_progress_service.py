from decimal import Decimal

from fastapi import status
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.core.uuid_codec import decode_course_uuid, decode_module_uuid
from app.models.module_progress import ProgressStatus
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_progress_repository import ModuleProgressRepository
from app.repositories.module_repository import ModuleRepository
from app.schemas.course import ModuleResponse
from app.schemas.module import ModuleProgressUpdateRequest
from app.services.course_catalog_service import CourseCatalogService
from app.services.module_profile_trigger_service import ModuleProfileTriggerService
from app.services.module_unlocking_service import ModuleUnlockingService
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error


class ModuleProgressService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.module_progress = ModuleProgressRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.catalog = CourseCatalogService(session)
        self.unlocking = ModuleUnlockingService(session)
        self.profile_triggers = ModuleProfileTriggerService(session)

    def update_progress(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        payload: ModuleProgressUpdateRequest,
        current_user: dict,
    ) -> ModuleResponse:
        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise invalid_identity_response_error()
        if current_user.get("identity") != "Learner":
            raise http_error(status_code=status.HTTP_403_FORBIDDEN, code="LEARNER_ONLY", message="Only learners can update module progress")

        course_id = decode_course_uuid(course_uuid)
        module_id = decode_module_uuid(module_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="COURSE_NOT_FOUND", message="Course not found")

        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        if learning_path is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="LEARNING_PATH_NOT_FOUND", message="Learning path not found")

        module = self.modules.get_by_id(module_id)
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")

        enrollment = self.enrollments.get_by_course_and_learner(course_id=course.course_id, learner_id=learner_id)
        if enrollment is None:
            raise http_error(status_code=status.HTTP_403_FORBIDDEN, code="ENROLLMENT_REQUIRED", message="Learner must be enrolled before progressing through modules")

        self.unlocking.ensure_module_unlocked(
            module_id=module.module_id,
            learner_id=learner_id,
            resource_name="module",
        )

        progress_status = self._parse_progress_status(payload.progressStatus)
        current_time = now_local()
        progress_percent = Decimal("100.00") if progress_status == ProgressStatus.COMPLETED else Decimal("50.00")
        completed_at = current_time if progress_status == ProgressStatus.COMPLETED else None

        progress = self.module_progress.get_by_module_and_learner(module.module_id, learner_id)
        was_completed = progress is not None and progress.progress_status == ProgressStatus.COMPLETED
        if progress is None:
            progress = self.module_progress.create(
                module_id=module.module_id,
                learner_id=learner_id,
                progress_status=progress_status,
                progress_percent=progress_percent,
                time_spent_seconds=0,
                started_at=current_time if progress_status != ProgressStatus.NOT_STARTED else None,
                last_accessed_at=current_time,
                completed_at=completed_at,
            )
        else:
            self.module_progress.update_progress(
                progress,
                progress_status=progress_status,
                progress_percent=progress_percent,
                time_spent_seconds=progress.time_spent_seconds,
                started_at=progress.started_at or (current_time if progress_status != ProgressStatus.NOT_STARTED else None),
                last_accessed_at=current_time,
                completed_at=completed_at,
            )

        self.session.commit()
        if progress_status == ProgressStatus.COMPLETED and not was_completed:
            self.profile_triggers.initialize_newly_unlocked_after_completion(
                course_id=course.course_id,
                completed_module_id=module.module_id,
                learner_id=learner_id,
            )
        return self.catalog.get_course_module_by_uuid(
            course_uuid=course_uuid,
            module_uuid=module_uuid,
            current_user=current_user,
        )

    def _ensure_module_unlocked(self, *, module_id: int, learner_id: int) -> None:
        self.unlocking.ensure_module_unlocked(
            module_id=module_id,
            learner_id=learner_id,
            resource_name="module",
        )

    def _parse_progress_status(self, status_value: str) -> ProgressStatus:
        normalized = status_value.strip().lower()
        try:
            return ProgressStatus(normalized)
        except ValueError as exc:
            raise invalid_request_error("progressStatus must be one of not_started, in_progress, completed") from exc
