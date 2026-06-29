from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.core.uuid_codec import decode_course_uuid, decode_module_uuid, encode_course_uuid, encode_module_uuid, encode_user_uuid
from app.models.courses import Course, CourseStatus, DifficultyLevelStatus
from app.models.modules import ModuleStatus
from app.models.quizzes import QuizStatus
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_material_repository import ModuleMaterialRepository
from app.repositories.module_progress_repository import ModuleProgressRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.module_repository import _UNSET
from app.repositories.quiz_question_option_repository import QuizQuestionOptionRepository
from app.repositories.quiz_question_repository import QuizQuestionRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.quiz_attempt_repository import QuizAttemptRepository
from app.repositories.short_answer_assessment_repository import ShortAnswerAssessmentRepository
from app.repositories.short_answer_submission_repository import ShortAnswerSubmissionRepository
from app.schemas.course import (
    AssessmentSignalInsightItem,
    AtRiskLearnerInsightItem,
    CompletionTrendInsightItem,
    CourseCreateRequest,
    CourseDetailResponse,
    CoursePublishRequest,
    CourseUpdateRequest,
    EducatorAnalyticsResponse,
    EducatorCourseAnalyticsItem,
    EducatorQuizAnalyticsResponse,
    EducatorTeachingInsightsResponse,
    ModuleBottleneckInsightItem,
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
        self.module_progress = ModuleProgressRepository(session)
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
        self.short_answer_assessments = ShortAnswerAssessmentRepository(session)
        self.short_answer_submissions = ShortAnswerSubmissionRepository(session)

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

    def get_educator_teaching_insights(self, *, current_user: dict) -> EducatorTeachingInsightsResponse:
        educator_id = current_user.get("id")
        if not isinstance(educator_id, int):
            raise invalid_identity_response_error()

        courses = self.courses.list_by_educator(educator_id)
        if not courses:
            return EducatorTeachingInsightsResponse(
                moduleBottlenecks=[],
                atRiskLearners=[],
                completionTrends=[],
                assessmentSignals=[],
            )

        quiz_rows_by_module = {
            row["module_id"]: row
            for row in self.quiz_attempts.aggregate_stats_by_educator(educator_id=educator_id)
        }
        module_bottlenecks: list[ModuleBottleneckInsightItem] = []
        at_risk_learners: list[AtRiskLearnerInsightItem] = []
        assessment_signals: list[AssessmentSignalInsightItem] = []
        completion_counts: dict[tuple[int, date], int] = defaultdict(int)
        course_titles: dict[int, str] = {}

        for course in courses:
            course_titles[course.course_id] = course.title
            learning_path = self.learning_paths.get_by_course_id(course.course_id)
            modules = self.modules.list_by_learning_path(learning_path.learning_path_id) if learning_path else []
            enrollments = self.enrollments.list_current_by_course(course.course_id)
            module_ids = [module.module_id for module in modules]
            current_learner_ids = [int(enrollment.learner_id) for enrollment in enrollments]
            progress_rows = self.module_progress.list_by_module_ids(
                module_ids,
                learner_ids=current_learner_ids,
            )
            module_stats = {
                row["module_id"]: row
                for row in self.module_progress.aggregate_stats_by_module_ids(
                    module_ids,
                    learner_ids=current_learner_ids,
                )
            }
            assessments = self.short_answer_assessments.list_by_module_ids(module_ids)
            assessment_by_module = {assessment.module_id: assessment for assessment in assessments}
            short_answer_stats = {
                row["assessment_id"]: row
                for row in self.short_answer_submissions.aggregate_stats_by_assessment_ids(
                    [assessment.short_answer_assessment_id for assessment in assessments]
                )
            }

            enrolled_count = len(enrollments)
            course_uuid = encode_course_uuid(course.course_id)

            for module in modules:
                stats = module_stats.get(module.module_id, {})
                started_count = int(stats.get("started_count") or 0)
                completed_count = int(stats.get("completed_count") or 0)
                avg_progress_percent = stats.get("avg_progress_percent")
                completion_rate = completed_count / enrolled_count if enrolled_count else None
                bottleneck_signals: list[str] = []
                if enrolled_count == 0:
                    bottleneck_signals.append("no_enrollments")
                elif started_count == 0:
                    bottleneck_signals.append("no_activity")
                if completion_rate is not None and completion_rate < 0.5:
                    bottleneck_signals.append("low_completion")
                if avg_progress_percent is not None and avg_progress_percent < 35:
                    bottleneck_signals.append("low_progress")

                module_bottlenecks.append(
                    ModuleBottleneckInsightItem(
                        courseUuid=course_uuid,
                        courseTitle=course.title,
                        moduleUuid=encode_module_uuid(module.module_id),
                        moduleTitle=module.title,
                        enrolledLearnerCount=enrolled_count,
                        startedLearnerCount=started_count,
                        completedLearnerCount=completed_count,
                        completionRate=completion_rate,
                        avgProgressPercent=avg_progress_percent,
                        signals=bottleneck_signals,
                    )
                )

            for enrollment in enrollments:
                total_module_count = int(getattr(enrollment, "total_module_count", 0) or len(modules))
                completed_module_count = int(getattr(enrollment, "completed_module_count", 0) or 0)
                incomplete_module_count = max(0, total_module_count - completed_module_count)
                progress_percent = self._to_float(getattr(enrollment, "progress_percent", 0)) or 0.0
                risk_reasons: list[str] = []
                if progress_percent < 35:
                    risk_reasons.append("low_progress")
                last_accessed_at = getattr(enrollment, "last_accessed_at", None)
                if last_accessed_at is None:
                    risk_reasons.append("no_recent_activity")
                elif self._is_older_than(last_accessed_at, days=14):
                    risk_reasons.append("inactive_14_days")
                incomplete_threshold = max(2, (total_module_count + 1) // 2) if total_module_count else 0
                if incomplete_threshold and incomplete_module_count >= incomplete_threshold:
                    risk_reasons.append("many_incomplete_modules")

                if risk_reasons:
                    learner_id = int(enrollment.learner_id)
                    at_risk_learners.append(
                        AtRiskLearnerInsightItem(
                            courseUuid=course_uuid,
                            courseTitle=course.title,
                            learnerId=learner_id,
                            learnerUuid=encode_user_uuid(learner_id),
                            progressPercent=progress_percent,
                            completedModuleCount=completed_module_count,
                            totalModuleCount=total_module_count,
                            incompleteModuleCount=incomplete_module_count,
                            lastAccessedAt=last_accessed_at,
                            riskReasons=risk_reasons,
                        )
                    )

            for progress in progress_rows:
                if progress.completed_at is not None:
                    completion_counts[(course.course_id, progress.completed_at.date())] += 1

            for module in modules:
                quiz_row = quiz_rows_by_module.get(module.module_id)
                assessment = assessment_by_module.get(module.module_id)
                if quiz_row is None and assessment is None:
                    continue

                short_stats = short_answer_stats.get(
                    assessment.short_answer_assessment_id if assessment is not None else -1,
                    {},
                )
                quiz_attempt_count = int(quiz_row["total_attempts"]) if quiz_row else 0
                quiz_avg_score = quiz_row.get("avg_score_percent") if quiz_row else None
                quiz_pass_rate = quiz_row.get("pass_rate") if quiz_row else None
                short_answer_submission_count = int(short_stats.get("submission_count") or 0)
                short_answer_pending_count = int(short_stats.get("pending_review_count") or 0)
                short_answer_avg_ai_score = short_stats.get("avg_ai_score")
                short_answer_avg_final_score = short_stats.get("avg_final_score")
                short_answer_max_score = self._to_float(assessment.max_score) if assessment is not None else None
                signal_codes: list[str] = []

                if quiz_row is not None:
                    if quiz_attempt_count == 0 and enrolled_count > 0:
                        signal_codes.append("quiz_no_attempts")
                    if quiz_attempt_count > 0 and quiz_pass_rate is not None and quiz_pass_rate < 0.6:
                        signal_codes.append("low_quiz_pass_rate")
                    if quiz_attempt_count > 0 and quiz_avg_score is not None and quiz_avg_score < 60:
                        signal_codes.append("low_quiz_avg_score")
                if short_answer_pending_count > 0:
                    signal_codes.append("short_answer_pending_review")
                score_for_signal = (
                    short_answer_avg_final_score
                    if short_answer_avg_final_score is not None
                    else short_answer_avg_ai_score
                )
                if (
                    score_for_signal is not None
                    and short_answer_max_score is not None
                    and short_answer_max_score > 0
                    and (score_for_signal / short_answer_max_score) < 0.6
                ):
                    signal_codes.append("low_short_answer_score")

                assessment_signals.append(
                    AssessmentSignalInsightItem(
                        courseUuid=course_uuid,
                        courseTitle=course.title,
                        moduleUuid=encode_module_uuid(module.module_id),
                        moduleTitle=module.title,
                        quizTitle=quiz_row.get("quiz_title") if quiz_row else None,
                        quizAttemptCount=quiz_attempt_count,
                        quizAvgScorePercent=quiz_avg_score,
                        quizPassRate=quiz_pass_rate,
                        shortAnswerTitle=assessment.title if assessment is not None else None,
                        shortAnswerSubmissionCount=short_answer_submission_count,
                        shortAnswerAvgAiScore=short_answer_avg_ai_score,
                        shortAnswerAvgFinalScore=short_answer_avg_final_score,
                        shortAnswerMaxScore=short_answer_max_score,
                        shortAnswerPendingReviewCount=short_answer_pending_count,
                        signals=signal_codes,
                    )
                )

        completion_trends = [
            CompletionTrendInsightItem(
                courseUuid=encode_course_uuid(course_id),
                courseTitle=course_titles[course_id],
                bucketDate=bucket_date,
                completedCount=count,
            )
            for (course_id, bucket_date), count in sorted(
                completion_counts.items(),
                key=lambda item: (item[0][1], item[0][0]),
            )
        ]

        at_risk_learners.sort(key=lambda item: (item.progressPercent, item.courseTitle, item.learnerId))
        assessment_signals.sort(key=lambda item: (item.courseTitle, item.moduleTitle))

        return EducatorTeachingInsightsResponse(
            moduleBottlenecks=module_bottlenecks,
            atRiskLearners=at_risk_learners,
            completionTrends=completion_trends,
            assessmentSignals=assessment_signals,
        )

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

    def _to_float(self, value: Decimal | float | int | None) -> float | None:
        if value is None:
            return None
        return float(value)

    def _is_older_than(self, value: datetime, *, days: int) -> bool:
        current = now_local()
        compared = value
        if compared.tzinfo is None and current.tzinfo is not None:
            current = current.replace(tzinfo=None)
        if compared.tzinfo is not None and current.tzinfo is None:
            compared = compared.replace(tzinfo=None)
        return compared < current - timedelta(days=days)
