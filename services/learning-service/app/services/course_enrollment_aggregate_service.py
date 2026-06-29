from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.core.time import now_local
from app.models.course_enrollments import EnrollmentStatus
from app.models.module_progress import ProgressStatus
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_progress_repository import ModuleProgressRepository
from app.repositories.module_repository import ModuleRepository


class CourseEnrollmentAggregateService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.enrollments = CourseEnrollmentRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.module_progress = ModuleProgressRepository(session)

    def build_initial_aggregate(self, *, course_id: int) -> tuple[int, Decimal]:
        total_module_count = self._get_published_module_count(course_id)
        progress_percent = self._calculate_progress_percent(
            completed_module_count=0,
            total_module_count=total_module_count,
        )
        return total_module_count, progress_percent

    def sync_total_module_count_for_course(self, *, course_id: int) -> None:
        total_module_count = self._get_published_module_count(course_id)
        for enrollment in self.enrollments.list_current_by_course(course_id):
            progress_percent = self._calculate_progress_percent(
                completed_module_count=enrollment.completed_module_count,
                total_module_count=total_module_count,
            )
            self.enrollments.update_progress(
                enrollment,
                progress_percent=progress_percent,
                completed_module_count=enrollment.completed_module_count,
                total_module_count=total_module_count,
            )

    def sync_all_learners_progress_for_course(self, *, course_id: int) -> None:
        for enrollment in self.enrollments.list_current_by_course(course_id):
            self.sync_learner_progress_for_course(course_id=course_id, learner_id=enrollment.learner_id)

    def touch_last_accessed(self, *, course_id: int, learner_id: int, accessed_at) -> None:
        enrollment = self.enrollments.get_by_course_and_learner(course_id=course_id, learner_id=learner_id)
        if enrollment is None:
            return
        self.enrollments.touch_last_accessed(enrollment, accessed_at=accessed_at)

    def sync_learner_progress_for_course(self, *, course_id: int, learner_id: int, accessed_at=None) -> None:
        enrollment = self.enrollments.get_by_course_and_learner(course_id=course_id, learner_id=learner_id)
        if enrollment is None:
            return

        learning_path = self.learning_paths.get_by_course_id(course_id)
        published_modules = self.modules.list_published_by_learning_path(learning_path.learning_path_id) if learning_path else []
        total_module_count = len(published_modules)
        completed_module_count = 0
        for module in published_modules:
            progress = self.module_progress.get_by_module_and_learner(module.module_id, learner_id)
            if progress is not None and progress.progress_status == ProgressStatus.COMPLETED:
                completed_module_count += 1

        progress_percent = self._calculate_progress_percent(
            completed_module_count=completed_module_count,
            total_module_count=total_module_count,
        )
        completed_at = now_local() if total_module_count > 0 and completed_module_count >= total_module_count else None

        self.enrollments.update_progress(
            enrollment,
            progress_percent=progress_percent,
            completed_module_count=completed_module_count,
            total_module_count=total_module_count,
            last_accessed_at=accessed_at if accessed_at is not None else enrollment.last_accessed_at,
            completed_at=completed_at,
        )
        self.enrollments.update_status(
            enrollment,
            enrollment_status=EnrollmentStatus.COMPLETED if completed_at is not None else EnrollmentStatus.ACTIVE,
            last_accessed_at=accessed_at if accessed_at is not None else enrollment.last_accessed_at,
            completed_at=completed_at,
        )

    def _get_published_module_count(self, course_id: int) -> int:
        learning_path = self.learning_paths.get_by_course_id(course_id)
        if learning_path is None:
            return 0
        return len(self.modules.list_published_by_learning_path(learning_path.learning_path_id))

    def _calculate_progress_percent(
        self,
        *,
        completed_module_count: int,
        total_module_count: int,
    ) -> Decimal:
        if total_module_count <= 0 or completed_module_count <= 0:
            return Decimal("0.00")

        percent = (Decimal(completed_module_count) / Decimal(total_module_count)) * Decimal("100")
        return percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
