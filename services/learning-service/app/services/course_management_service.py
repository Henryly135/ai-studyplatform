from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
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
    EducatorMaterialBriefItem,
    EducatorMaterialBriefsResponse,
    EducatorQuizAnalyticsResponse,
    EducatorTeachingInsightsResponse,
    QuizModuleStatsItem,
    TeachingInsightItem,
)
from app.services.ai_index_job_client import AIIndexJobClient
from app.services.course_catalog_service import CourseCatalogService
from app.services.course_enrollment_aggregate_service import CourseEnrollmentAggregateService
from app.services.module_material_service import ModuleMaterialService
from app.services.storage_service import StorageService, StoredFile, normalize_local_material_object_key
from app.services.upload_scan_service import UploadScanFailure, UploadScanService
from platform_common.errors import http_error, invalid_identity_response_error, invalid_request_error


_ALLOWED_COVER_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_COVER_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MATERIAL_BRIEF_TEXT_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
}
_MATERIAL_BRIEF_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json"}
_MATERIAL_BRIEF_MAX_TEXT_BYTES = 64 * 1024
_MATERIAL_BRIEF_OBJECTIVE_TERMS = {"objective", "outcome", "goal", "you will learn", "by the end"}
_MATERIAL_BRIEF_EXAMPLE_TERMS = {"example", "worked example", "walkthrough", "case study", "sample"}
_MATERIAL_BRIEF_PRACTICE_TERMS = {"practice", "exercise", "checkpoint", "try it", "quiz", "question"}
_MATERIAL_BRIEF_PREREQUISITE_TERMS = {"prerequisite", "assume", "before you start", "prior knowledge", "background"}
_MATERIAL_BRIEF_ADVANCED_TERMS = {
    "advanced",
    "complex",
    "proof",
    "theorem",
    "derive",
    "optimization",
    "edge case",
    "debug",
    "architecture",
}


@dataclass(frozen=True)
class _MaterialBriefTextSignal:
    extracted_count: int
    total_chars: int
    labels: tuple[str, ...]
    has_worked_examples: bool
    has_practice: bool
    has_prerequisites: bool
    has_advanced_terms: bool


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
        self.upload_scanner = UploadScanService()
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
                self._validate_course_cover_upload(cover_image)
                stored_cover_image = self.storage.store_course_cover(course_uuid=course_uuid, upload=cover_image)
                self.courses.update(
                    course,
                    cover_image_url=stored_cover_image.public_url,
                )

            self.session.commit()
            self.session.refresh(course)
        except Exception:
            self.session.rollback()
            self._delete_stored_course_cover_quietly(course_uuid=course_uuid, stored_cover_image=stored_cover_image)
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
            self._validate_course_cover_upload(cover_image)
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
            self._delete_stored_course_cover_quietly(course_uuid=course_uuid, stored_cover_image=stored_cover_image)
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

    def _validate_course_cover_upload(self, upload: UploadFile) -> None:
        normalized_content_type = (upload.content_type or "").strip().lower()
        filename = upload.filename or ""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        normalized_extension = f".{extension}" if extension else ""

        if normalized_content_type not in _ALLOWED_COVER_IMAGE_CONTENT_TYPES and (
            normalized_content_type or normalized_extension not in _ALLOWED_COVER_IMAGE_EXTENSIONS
        ):
            raise invalid_request_error("Course cover must be a JPEG, PNG, WebP, or GIF image")

        size_bytes = self._get_upload_size(upload)
        if size_bytes is not None and size_bytes > settings.max_material_upload_bytes:
            raise invalid_request_error(
                f"Course cover image is too large. Maximum is {settings.max_material_upload_bytes} bytes."
            )

        try:
            self.upload_scanner.scan_upload(upload, label=filename or "course-cover")
        except UploadScanFailure as exc:
            raise invalid_request_error(str(exc)) from exc

    def _get_upload_size(self, upload: UploadFile) -> int | None:
        size = getattr(upload, "size", None)
        if isinstance(size, int) and size >= 0:
            return size

        try:
            current_position = upload.file.tell()
            upload.file.seek(0, 2)
            size_bytes = upload.file.tell()
            upload.file.seek(current_position)
            return size_bytes
        except (AttributeError, OSError):
            return None

    def _delete_stored_course_cover_quietly(
        self,
        *,
        course_uuid: str,
        stored_cover_image: StoredFile | None,
    ) -> None:
        if stored_cover_image is None:
            return
        try:
            self.storage.delete_course_cover(
                course_uuid=course_uuid,
                cover_image_url=stored_cover_image.public_url,
            )
        except Exception:
            pass

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

    def get_educator_teaching_insights(self, *, current_user: dict) -> EducatorTeachingInsightsResponse:
        educator_id = current_user.get("id")
        if not isinstance(educator_id, int):
            raise invalid_identity_response_error()

        course_rows = self.enrollments.aggregate_stats_by_educator(educator_id=educator_id)
        quiz_rows = self.quiz_attempts.aggregate_stats_by_educator(educator_id=educator_id)
        insights: list[TeachingInsightItem] = []

        for row in course_rows:
            course_uuid = encode_course_uuid(row["course_id"])
            course_title = row["course_title"]
            total_enrollments = int(row["total_enrollments"] or 0)
            active_enrollments = int(row["active_enrollments"] or 0)
            completed_enrollments = int(row["completed_enrollments"] or 0)
            avg_progress = row["avg_progress_percent"]

            if total_enrollments == 0:
                insights.append(
                    TeachingInsightItem(
                        insightId=f"course-{row['course_id']}-no-enrolments",
                        priority="medium",
                        category="course_launch",
                        title="Invite learners to start this course",
                        detail=f"{course_title} is published but has no learner enrolments yet.",
                        actionLabel="Share course or invite link",
                        courseUuid=course_uuid,
                        courseTitle=course_title,
                        metricLabel="Enrolments",
                        metricValue="0",
                    )
                )
            elif avg_progress is not None and avg_progress < 40 and active_enrollments > 0:
                insights.append(
                    TeachingInsightItem(
                        insightId=f"course-{row['course_id']}-low-progress",
                        priority="high",
                        category="learner_progress",
                        title="Review low course progress",
                        detail=f"{course_title} has {active_enrollments} active learners with average progress below 40%.",
                        actionLabel="Check modules and send guidance",
                        courseUuid=course_uuid,
                        courseTitle=course_title,
                        metricLabel="Average progress",
                        metricValue=f"{round(float(avg_progress))}%",
                    )
                )
            elif total_enrollments > 0 and completed_enrollments == 0 and active_enrollments >= 3:
                insights.append(
                    TeachingInsightItem(
                        insightId=f"course-{row['course_id']}-no-completions",
                        priority="medium",
                        category="learner_progress",
                        title="No learners have completed this course yet",
                        detail=f"{course_title} has learner activity, but no completion records.",
                        actionLabel="Review prerequisites and assessment difficulty",
                        courseUuid=course_uuid,
                        courseTitle=course_title,
                        metricLabel="Completions",
                        metricValue="0",
                    )
                )

        for row in quiz_rows:
            course_uuid = encode_course_uuid(row["course_id"])
            module_uuid = encode_module_uuid(row["module_id"])
            total_attempts = int(row["total_attempts"] or 0)
            avg_score = row["avg_score_percent"]
            pass_rate = row["pass_rate"]
            avg_duration = row["avg_duration_seconds"]

            if total_attempts == 0:
                insights.append(
                    TeachingInsightItem(
                        insightId=f"quiz-{row['module_id']}-no-attempts",
                        priority="medium",
                        category="quiz_engagement",
                        title="Published quiz has no attempts",
                        detail=f"Learners have not attempted {row['quiz_title']} in {row['module_title']} yet.",
                        actionLabel="Add a prompt in the module or announcement",
                        courseUuid=course_uuid,
                        courseTitle=row["course_title"],
                        moduleUuid=module_uuid,
                        moduleTitle=row["module_title"],
                        metricLabel="Attempts",
                        metricValue="0",
                    )
                )
            elif pass_rate is not None and pass_rate < 0.6 and total_attempts >= 3:
                insights.append(
                    TeachingInsightItem(
                        insightId=f"quiz-{row['module_id']}-low-pass-rate",
                        priority="high",
                        category="quiz_difficulty",
                        title="Quiz pass rate needs review",
                        detail=f"{row['quiz_title']} has a pass rate below 60% across {total_attempts} attempts.",
                        actionLabel="Review explanations and prerequisite material",
                        courseUuid=course_uuid,
                        courseTitle=row["course_title"],
                        moduleUuid=module_uuid,
                        moduleTitle=row["module_title"],
                        metricLabel="Pass rate",
                        metricValue=f"{round(float(pass_rate) * 100)}%",
                    )
                )
            elif avg_score is not None and avg_score < 70 and total_attempts >= 2:
                insights.append(
                    TeachingInsightItem(
                        insightId=f"quiz-{row['module_id']}-low-score",
                        priority="medium",
                        category="quiz_difficulty",
                        title="Average quiz score is low",
                        detail=f"{row['quiz_title']} average score is below 70%.",
                        actionLabel="Add worked examples before the quiz",
                        courseUuid=course_uuid,
                        courseTitle=row["course_title"],
                        moduleUuid=module_uuid,
                        moduleTitle=row["module_title"],
                        metricLabel="Average score",
                        metricValue=f"{round(float(avg_score))}%",
                    )
                )
            elif avg_duration is not None and avg_duration > 900 and total_attempts >= 2:
                insights.append(
                    TeachingInsightItem(
                        insightId=f"quiz-{row['module_id']}-long-duration",
                        priority="low",
                        category="quiz_timing",
                        title="Quiz may be taking too long",
                        detail=f"{row['quiz_title']} average duration is above 15 minutes.",
                        actionLabel="Check wording and time limit",
                        courseUuid=course_uuid,
                        courseTitle=row["course_title"],
                        moduleUuid=module_uuid,
                        moduleTitle=row["module_title"],
                        metricLabel="Average duration",
                        metricValue=f"{round(float(avg_duration) / 60)} min",
                    )
                )

        priority_rank = {"high": 0, "medium": 1, "low": 2}
        insights.sort(key=lambda item: (priority_rank.get(item.priority, 9), item.category, item.title))
        limited_items = insights[:8]
        return EducatorTeachingInsightsResponse(
            generatedAt=now_local(),
            totalInsights=len(insights),
            highPriorityCount=sum(1 for item in insights if item.priority == "high"),
            items=limited_items,
        )

    def get_educator_material_briefs(self, *, current_user: dict) -> EducatorMaterialBriefsResponse:
        educator_id = current_user.get("id")
        if not isinstance(educator_id, int):
            raise invalid_identity_response_error()

        quiz_stats_by_module = {
            int(row["module_id"]): row
            for row in self.quiz_attempts.aggregate_stats_by_educator(educator_id=educator_id)
        }
        briefs: list[EducatorMaterialBriefItem] = []

        for course in self.courses.list_by_educator(educator_id):
            learning_path = getattr(course, "learning_path", None)
            learning_path_id = getattr(learning_path, "learning_path_id", None)
            if learning_path_id is None:
                continue

            for module in self.modules.list_by_learning_path(learning_path_id):
                materials = self.materials.list_by_module(module.module_id)
                material_types = self._format_material_types(materials)
                quiz_stats = quiz_stats_by_module.get(module.module_id)
                text_signal = self._build_material_text_signal(materials)
                priority, difficulty_signal, recommended_action = self._build_material_brief_signal(
                    material_count=len(materials),
                    material_types=material_types,
                    quiz_stats=quiz_stats,
                    text_signal=text_signal,
                )
                summary = self._build_material_brief_summary(
                    module_title=module.title,
                    material_count=len(materials),
                    material_types=material_types,
                    quiz_stats=quiz_stats,
                    text_signal=text_signal,
                )

                briefs.append(
                    EducatorMaterialBriefItem(
                        briefId=f"module-{module.module_id}-material-brief",
                        priority=priority,
                        courseUuid=encode_course_uuid(course.course_id),
                        courseTitle=course.title,
                        moduleUuid=encode_module_uuid(module.module_id),
                        moduleTitle=module.title,
                        moduleStatus=self._enum_value(module.status),
                        materialCount=len(materials),
                        materialTypes=material_types,
                        quizTitle=quiz_stats["quiz_title"] if quiz_stats else None,
                        passRate=float(quiz_stats["pass_rate"]) if quiz_stats and quiz_stats["pass_rate"] is not None else None,
                        averageScorePercent=(
                            float(quiz_stats["avg_score_percent"])
                            if quiz_stats and quiz_stats["avg_score_percent"] is not None
                            else None
                        ),
                        summary=summary,
                        difficultySignal=difficulty_signal,
                        recommendedAction=recommended_action,
                    )
                )

        priority_rank = {"high": 0, "medium": 1, "low": 2}
        briefs.sort(key=lambda item: (priority_rank.get(item.priority, 9), item.courseTitle, item.moduleTitle))
        limited_items = briefs[:8]
        return EducatorMaterialBriefsResponse(
            generatedAt=now_local(),
            totalBriefs=len(briefs),
            highPriorityCount=sum(1 for item in briefs if item.priority == "high"),
            items=limited_items,
        )

    def _format_material_types(self, materials: list[object]) -> list[str]:
        return sorted(
            {
                self._enum_value(getattr(material, "material_type", "file")).strip().lower()
                for material in materials
                if self._enum_value(getattr(material, "material_type", "file")).strip()
            }
        )

    def _build_material_brief_summary(
        self,
        *,
        module_title: str,
        material_count: int,
        material_types: list[str],
        quiz_stats: dict | None,
        text_signal: _MaterialBriefTextSignal | None,
    ) -> str:
        material_label = "no materials" if material_count == 0 else f"{material_count} materials"
        type_label = ", ".join(material_types) if material_types else "no material types"
        text_signal_sentence = self._format_material_text_signal_sentence(text_signal)
        if not quiz_stats:
            return f"{module_title} currently has {material_label} ({type_label}) and no quiz signal yet.{text_signal_sentence}"
        attempts = int(quiz_stats["total_attempts"] or 0)
        pass_rate = quiz_stats["pass_rate"]
        if pass_rate is None:
            return f"{module_title} currently has {material_label} ({type_label}); the quiz has no attempts yet.{text_signal_sentence}"
        return (
            f"{module_title} currently has {material_label} ({type_label}); "
            f"quiz pass rate is {round(float(pass_rate) * 100)}% across {attempts} attempts.{text_signal_sentence}"
        )

    def _build_material_brief_signal(
        self,
        *,
        material_count: int,
        material_types: list[str],
        quiz_stats: dict | None,
        text_signal: _MaterialBriefTextSignal | None,
    ) -> tuple[str, str, str]:
        if material_count == 0:
            return (
                "high",
                "No learning materials are attached to this module.",
                "Add at least one learner-facing material before asking students to use AI or attempt the quiz.",
            )

        if quiz_stats:
            attempts = int(quiz_stats["total_attempts"] or 0)
            pass_rate = quiz_stats["pass_rate"]
            average_score = quiz_stats["avg_score_percent"]
            if pass_rate is not None and pass_rate < 0.6 and attempts >= 3:
                if text_signal and text_signal.extracted_count and not (
                    text_signal.has_worked_examples or text_signal.has_practice
                ):
                    return (
                        "high",
                        f"Quiz pass rate is below 60% across {attempts} attempts, and extracted material text lacks explicit example or practice cues.",
                        "Add worked examples and practice checkpoints before students attempt the quiz again.",
                    )
                return (
                    "high",
                    f"Quiz pass rate is below 60% across {attempts} attempts.",
                    "Review material explanations, add worked examples, and check whether quiz questions rely on unstated prerequisites.",
                )
            if average_score is not None and average_score < 70 and attempts >= 2:
                if text_signal and text_signal.extracted_count and not text_signal.has_worked_examples:
                    return (
                        "medium",
                        "Average quiz score is below 70%, and extracted material text does not show worked-example cues.",
                        "Add a short worked solution or guided example before the quiz and review distractor wording.",
                    )
                return (
                    "medium",
                    "Average quiz score is below 70%.",
                    "Add a short recap or practice activity before the quiz and review distractor wording.",
                )

        if text_signal and text_signal.extracted_count and text_signal.has_advanced_terms and not text_signal.has_prerequisites:
            return (
                "medium",
                "Extracted material text includes advanced or technical cues without clear prerequisite guidance.",
                "Add a short prerequisite note or warm-up section before learners enter the advanced material.",
            )

        if not quiz_stats:
            return (
                "medium",
                "No quiz or learner performance signal is available for this module.",
                "Add or publish a quiz so material effectiveness can be measured.",
            )

        if text_signal and text_signal.extracted_count and not (
            text_signal.has_worked_examples or text_signal.has_practice
        ):
            return (
                "low",
                "Extracted material text lacks clear worked-example or practice cues.",
                "Add one worked example, practice prompt, or checkpoint to make the material easier to act on.",
            )

        if material_count == 1:
            return (
                "low",
                "Only one material type is available for this module.",
                "Consider adding a second representation such as notes, worked examples, or a short video.",
            )

        if material_types == ["video"]:
            return (
                "low",
                "The module relies only on video material.",
                "Add a text summary or downloadable reference so learners can review key points quickly.",
            )

        return (
            "low",
            "Materials and quiz signals do not show an urgent issue.",
            "Keep monitoring learner questions and quiz results after the next cohort activity.",
        )

    def _build_material_text_signal(self, materials: list[object]) -> _MaterialBriefTextSignal | None:
        text_payloads = []
        for material in materials:
            text_payload = self._extract_material_text(material)
            if text_payload:
                text_payloads.append(text_payload)

        if not text_payloads:
            return None

        combined_text = "\n".join(text_payloads).lower()
        labels: list[str] = []
        has_objectives = self._contains_any(combined_text, _MATERIAL_BRIEF_OBJECTIVE_TERMS)
        has_worked_examples = self._contains_any(combined_text, _MATERIAL_BRIEF_EXAMPLE_TERMS)
        has_practice = self._contains_any(combined_text, _MATERIAL_BRIEF_PRACTICE_TERMS)
        has_prerequisites = self._contains_any(combined_text, _MATERIAL_BRIEF_PREREQUISITE_TERMS)
        has_advanced_terms = self._contains_any(combined_text, _MATERIAL_BRIEF_ADVANCED_TERMS)

        if has_objectives:
            labels.append("learning objectives")
        if has_worked_examples:
            labels.append("worked examples")
        if has_practice:
            labels.append("practice checkpoints")
        if has_prerequisites:
            labels.append("prerequisite guidance")
        if has_advanced_terms:
            labels.append("advanced concept cues")

        return _MaterialBriefTextSignal(
            extracted_count=len(text_payloads),
            total_chars=sum(len(payload) for payload in text_payloads),
            labels=tuple(labels),
            has_worked_examples=has_worked_examples,
            has_practice=has_practice,
            has_prerequisites=has_prerequisites,
            has_advanced_terms=has_advanced_terms,
        )

    def _extract_material_text(self, material: object) -> str | None:
        metadata = getattr(material, "metadata_json", None)
        if not isinstance(metadata, dict):
            return None

        storage_provider = str(metadata.get("storageProvider") or "").strip().lower()
        if storage_provider not in {"local", "minio"}:
            return None

        object_key = metadata.get("objectKey") or metadata.get("storedRelativePath")
        if not isinstance(object_key, str) or not object_key.strip():
            return None

        content_type = str(metadata.get("contentType") or "").strip().lower()
        if not self._is_text_material(content_type=content_type, object_key=object_key):
            return None

        if storage_provider == "minio":
            return self._extract_minio_material_text(
                bucket=metadata.get("bucket"),
                object_key=object_key,
            )

        return self._extract_local_material_text(object_key)

    def _extract_local_material_text(self, object_key: str) -> str | None:
        try:
            normalized_object_key = normalize_local_material_object_key(object_key)
            material_root = settings.material_root_path
            target_path = (material_root / normalized_object_key).resolve()
            target_path.relative_to(material_root.resolve())
        except (OSError, ValueError):
            return None

        if not target_path.is_file():
            return None

        try:
            payload = target_path.read_bytes()[:_MATERIAL_BRIEF_MAX_TEXT_BYTES]
        except OSError:
            return None

        return self._decode_material_brief_text(payload)

    def _extract_minio_material_text(self, *, bucket: object, object_key: str) -> str | None:
        try:
            normalized_object_key = normalize_local_material_object_key(object_key)
        except ValueError:
            return None

        bucket_name = str(bucket or settings.minio_bucket or "").strip()
        if not bucket_name:
            return None

        response = None
        try:
            client = self.storage._build_minio_client()
            response = client.get_object(bucket_name, normalized_object_key)
            payload = response.read(_MATERIAL_BRIEF_MAX_TEXT_BYTES)
        except Exception:
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
                try:
                    response.release_conn()
                except Exception:
                    pass

        return self._decode_material_brief_text(payload)

    def _is_text_material(self, *, content_type: str, object_key: str) -> bool:
        if content_type in _MATERIAL_BRIEF_TEXT_CONTENT_TYPES:
            return True
        return Path(object_key).suffix.lower() in _MATERIAL_BRIEF_TEXT_SUFFIXES

    def _decode_material_brief_text(self, payload: bytes) -> str | None:
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                text = payload.decode(encoding)
                normalized = " ".join(text.split())
                return normalized or None
            except UnicodeDecodeError:
                continue
        return None

    def _format_material_text_signal_sentence(self, text_signal: _MaterialBriefTextSignal | None) -> str:
        if not text_signal or not text_signal.extracted_count:
            return ""

        material_label = (
            "1 text-backed material"
            if text_signal.extracted_count == 1
            else f"{text_signal.extracted_count} text-backed materials"
        )
        signal_label = ", ".join(text_signal.labels[:4]) if text_signal.labels else "general explanations"
        return f" Text scan found {material_label} with {signal_label}."

    def _contains_any(self, text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)

    def _enum_value(self, value: object) -> str:
        return str(getattr(value, "value", value))

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
