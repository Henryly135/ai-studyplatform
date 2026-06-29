from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.core.uuid_codec import decode_course_uuid, decode_module_uuid, encode_course_uuid, encode_module_uuid
from app.models.courses import Course, CourseStatus, DifficultyLevelStatus
from app.models.modules import ModuleStatus
from app.models.quizzes import QuizStatus
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_material_repository import ModuleMaterialRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.module_repository import _UNSET
from app.repositories.quiz_question_option_repository import QuizQuestionOptionRepository
from app.repositories.quiz_question_repository import QuizQuestionRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.quiz_attempt_repository import QuizAttemptRepository
from app.schemas.course import (
    CourseCreateRequest,
    CourseDetailResponse,
    CoursePublishRequest,
    CourseUpdateRequest,
    EducatorAnalyticsResponse,
    EducatorCourseAnalyticsItem,
    EducatorQuizAnalyticsResponse,
    QuizModuleStatsItem,
)
from app.services.ai_index_job_client import AIIndexJobClient
from app.services.course_catalog_service import CourseCatalogService
from app.services.course_enrollment_aggregate_service import CourseEnrollmentAggregateService
from app.services.module_material_service import ModuleMaterialService
from app.services.storage_service import StorageService
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error


class CourseManagementService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.materials = ModuleMaterialRepository(session)
        self.ai_index_jobs = AIIndexJobClient()
        self.catalog = CourseCatalogService(session)
        self.enrollment_aggregates = CourseEnrollmentAggregateService(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.quiz_attempts = QuizAttemptRepository(session)
        self.storage = StorageService()
        self.material_service = ModuleMaterialService(session)
        self.quizzes = QuizRepository(session)
        self.quiz_questions = QuizQuestionRepository(session)
        self.quiz_options = QuizQuestionOptionRepository(session)

    def create_course(
        self,
        *,
        payload: CourseCreateRequest,
        current_user: dict,
        cover_image: UploadFile | None = None,
    ) -> CourseDetailResponse:
        educator_id = current_user.get("id")
        if not isinstance(educator_id, int):
            raise invalid_identity_response_error()

        normalized_title = payload.title.strip()
        if not normalized_title:
            raise invalid_request_error("Course title is required")

        difficulty_level = self._parse_difficulty_level(payload.difficultyLevel)

        course = self.courses.create(
            educator_id=educator_id,
            title=normalized_title,
            subtitle=self._normalize_optional_text(payload.subtitle),
            description=self._normalize_optional_text(payload.description),
            cover_image_url=None,
            status=CourseStatus.DRAFT,
            difficulty_level=difficulty_level,
            estimated_minutes=payload.estimatedMinutes,
            category=self._normalize_optional_text(payload.category),
            language_code=self._normalize_optional_text(payload.languageCode),
            is_public=payload.isPublic,
        )

        learning_path = self.learning_paths.create(
            course_id=course.course_id,
            title=self._build_learning_path_title(payload=payload, course=course),
            description=self._normalize_optional_text(payload.learningPathDescription),
        )

        course_uuid = encode_course_uuid(course.course_id)
        stored_cover_image = None

        try:
            if cover_image is not None:
                stored_cover_image = self.storage.store_course_cover(course_uuid=course_uuid, upload=cover_image)
                self.courses.update(
                    course,
                    cover_image_url=stored_cover_image.public_url,
                )

            self.session.commit()
            self.session.refresh(course)
        except Exception:
            self.session.rollback()
            if stored_cover_image is not None:
                self._delete_file_if_exists(stored_cover_image.absolute_path)
            raise

        return self.catalog.get_course_by_id(course_id=course.course_id, current_user=current_user)

    def publish_course(
        self,
        *,
        course_uuid: str,
        payload: CoursePublishRequest,
        current_user: dict,
    ) -> CourseDetailResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        if learning_path is None:
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LEARNING_PATH_NOT_FOUND",
                message="Learning path not found",
            )

        all_modules = self.modules.list_by_learning_path(learning_path.learning_path_id)
        if not all_modules:
            raise invalid_request_error("Course must contain at least one module before publishing")

        selected_module_ids: list[int] = []
        seen_module_ids: set[int] = set()
        for module_uuid in payload.moduleUuids:
            module_id = decode_module_uuid(module_uuid)
            if module_id in seen_module_ids:
                raise invalid_request_error("moduleUuids must not contain duplicates")
            seen_module_ids.add(module_id)
            selected_module_ids.append(module_id)

        selected_modules = self.modules.list_by_ids(selected_module_ids)
        if len(selected_modules) != len(selected_module_ids):
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")

        selected_module_by_id = {module.module_id: module for module in selected_modules}
        ordered_selected_modules: list = []

        for module_id in selected_module_ids:
            module = selected_module_by_id.get(module_id)
            if module is None or module.learning_path_id != learning_path.learning_path_id:
                raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="MODULE_NOT_FOUND", message="Module not found")
            if not module.content or not module.content.strip():
                raise invalid_request_error(f"Module {module.title} must have content before publishing")
            if not self.materials.list_by_module(module.module_id):
                raise invalid_request_error(f"Module {module.title} must contain at least one material before publishing")
            ordered_selected_modules.append(module)

        for module in ordered_selected_modules:
            self.modules.update(
                module,
                status=ModuleStatus.PUBLISHED,
                visible_to_class_id=None,
            )
            self._try_auto_publish_quiz(module.module_id)

        self.ai_index_jobs.release_blocked_jobs(
            course_id=course.course_id,
            module_ids=[module.module_id for module in ordered_selected_modules],
        )

        self.courses.update_status(
            course,
            status=CourseStatus.PUBLISHED,
            is_public=True,
            published_at=course.published_at or now_local(),
        )
        self.enrollment_aggregates.sync_total_module_count_for_course(course_id=course.course_id)
        self.session.commit()
        self.session.refresh(course)
        return self.catalog.get_course_by_id(course_id=course.course_id, current_user=current_user)

    def _try_auto_publish_quiz(self, module_id: int) -> None:
        """Auto-publish a module's quiz if it exists and passes validation. Silently skips if not ready."""
        quiz = self.quizzes.get_by_module_id(module_id)
        if quiz is None or quiz.status == QuizStatus.PUBLISHED:
            return
        active_questions = self.quiz_questions.list_active_by_quiz(quiz.quiz_id)
        if len(active_questions) < quiz.question_count_per_attempt:
            return
        for question in active_questions:
            options = self.quiz_options.list_by_question(question.quiz_question_id)
            if len(options) < 2 or sum(1 for o in options if o.is_correct) != 1:
                return
        self.quizzes.update(quiz, status=QuizStatus.PUBLISHED, published_at=now_local())

    def update_course(
        self,
        *,
        course_uuid: str,
        payload: CourseUpdateRequest,
        current_user: dict,
    ) -> CourseDetailResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self.learning_paths.get_by_course_id(course.course_id)

        normalized_title = (
            self._normalize_required_text(payload.title, field_name="title")
            if payload.title is not None
            else _UNSET
        )
        normalized_subtitle = self._normalize_optional_text(payload.subtitle) if payload.subtitle is not None else _UNSET
        normalized_description = (
            self._normalize_optional_text(payload.description)
            if payload.description is not None
            else _UNSET
        )
        normalized_cover_image_url = (
            self._normalize_optional_text(payload.coverImageUrl)
            if payload.coverImageUrl is not None
            else _UNSET
        )
        difficulty_level = self._parse_difficulty_level(payload.difficultyLevel) if payload.difficultyLevel is not None else _UNSET
        estimated_minutes = payload.estimatedMinutes if payload.estimatedMinutes is not None else _UNSET
        normalized_category = self._normalize_optional_text(payload.category) if payload.category is not None else _UNSET
        normalized_language_code = (
            self._normalize_optional_text(payload.languageCode)
            if payload.languageCode is not None
            else _UNSET
        )
        is_public = payload.isPublic if payload.isPublic is not None else _UNSET

        self.courses.update(
            course,
            title=normalized_title,
            subtitle=normalized_subtitle,
            description=normalized_description,
            cover_image_url=normalized_cover_image_url,
            difficulty_level=difficulty_level,
            estimated_minutes=estimated_minutes,
            category=normalized_category,
            language_code=normalized_language_code,
            is_public=is_public,
        )

        if learning_path is not None:
            learning_path_title = (
                self._normalize_required_text(payload.learningPathTitle, field_name="learningPathTitle")
                if payload.learningPathTitle is not None
                else _UNSET
            )
            learning_path_description = (
                self._normalize_optional_text(payload.learningPathDescription)
                if payload.learningPathDescription is not None
                else _UNSET
            )
            self.learning_paths.update(
                learning_path,
                title=learning_path_title,
                description=learning_path_description,
            )

        self.courses.touch(course)
        self.session.commit()
        self.session.refresh(course)

        return self.catalog.get_course_by_id(course_id=course.course_id, current_user=current_user)

    def update_course_cover(
        self,
        *,
        course_uuid: str,
        cover_image: UploadFile,
        current_user: dict,
    ) -> CourseDetailResponse:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        stored_cover_image = None

        try:
            stored_cover_image = self.storage.store_course_cover(course_uuid=course_uuid, upload=cover_image)
            self.courses.update(
                course,
                cover_image_url=stored_cover_image.public_url,
            )
            self.courses.touch(course)
            self.session.commit()
            self.session.refresh(course)
        except Exception:
            self.session.rollback()
            if stored_cover_image is not None:
                self._delete_file_if_exists(stored_cover_image.absolute_path)
            raise

        return self.catalog.get_course_by_id(course_id=course.course_id, current_user=current_user)

    def delete_course(
        self,
        *,
        course_uuid: str,
        current_user: dict,
    ) -> None:
        course = self._get_manageable_course(course_uuid=course_uuid, current_user=current_user)
        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        course_modules = (
            self.modules.list_by_learning_path(learning_path.learning_path_id)
            if learning_path is not None
            else []
        )

        for module in course_modules:
            for material in self.materials.list_by_module(module.module_id):
                self.material_service.cleanup_material_dependencies(material=material)

        self.storage.delete_course_cover(
            course_uuid=course_uuid,
            cover_image_url=course.cover_image_url,
        )
        self.courses.delete(course)
        self.session.commit()

    def _parse_difficulty_level(self, difficulty_level: str | None) -> DifficultyLevelStatus | None:
        if difficulty_level is None:
            return None

        normalized = difficulty_level.strip().lower()
        if not normalized:
            return None

        try:
            return DifficultyLevelStatus(normalized)
        except ValueError as exc:
            raise invalid_request_error(
                "difficultyLevel must be one of beginner, intermediate, advanced"
            ) from exc

    def _build_learning_path_title(self, *, payload: CourseCreateRequest, course: Course) -> str:
        custom_title = self._normalize_optional_text(payload.learningPathTitle)
        if custom_title:
            return custom_title
        return f"{course.title} Learning Path"

    def _get_manageable_course(self, *, course_uuid: str, current_user: dict) -> Course:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise http_error(status_code=status.HTTP_404_NOT_FOUND, code="COURSE_NOT_FOUND", message="Course not found")

        if current_user.get("identity") == "Admin":
            return course

        if course.educator_id != actor_id:
            raise http_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="COURSE_OWNERSHIP_REQUIRED",
                message="You can only manage your own courses",
            )
        return course

    def get_educator_analytics(self, *, current_user: dict) -> EducatorAnalyticsResponse:
        educator_id = current_user.get("id")
        if not isinstance(educator_id, int):
            raise invalid_identity_response_error()

        rows = self.enrollments.aggregate_stats_by_educator(educator_id=educator_id)
        courses = [
            EducatorCourseAnalyticsItem(
                courseUuid=encode_course_uuid(row["course_id"]),
                courseTitle=row["course_title"],
                status=row["status"],
                totalEnrollments=row["total_enrollments"],
                activeEnrollments=row["active_enrollments"],
                completedEnrollments=row["completed_enrollments"],
                avgProgressPercent=row["avg_progress_percent"],
            )
            for row in rows
        ]
        return EducatorAnalyticsResponse(
            courses=courses,
            totalCourses=len(courses),
            totalEnrollments=sum(c.totalEnrollments for c in courses),
            totalActiveEnrollments=sum(c.activeEnrollments for c in courses),
            totalCompletedEnrollments=sum(c.completedEnrollments for c in courses),
        )

    def get_educator_quiz_analytics(self, *, current_user: dict) -> EducatorQuizAnalyticsResponse:
        educator_id = current_user.get("id")
        if not isinstance(educator_id, int):
            raise invalid_identity_response_error()

        rows = self.quiz_attempts.aggregate_stats_by_educator(educator_id=educator_id)
        items = [
            QuizModuleStatsItem(
                courseUuid=encode_course_uuid(row["course_id"]),
                courseTitle=row["course_title"],
                moduleUuid=encode_module_uuid(row["module_id"]),
                moduleTitle=row["module_title"],
                quizTitle=row["quiz_title"],
                totalAttempts=row["total_attempts"],
                uniqueLearners=row["unique_learners"],
                avgScorePercent=row["avg_score_percent"],
                passRate=row["pass_rate"],
                avgDurationSeconds=row["avg_duration_seconds"],
            )
            for row in rows
        ]
        return EducatorQuizAnalyticsResponse(items=items)

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _normalize_required_text(self, value: str | None, *, field_name: str) -> str:
        normalized = self._normalize_optional_text(value)
        if not normalized:
            raise invalid_request_error(f"Course {field_name} is required")
        return normalized
