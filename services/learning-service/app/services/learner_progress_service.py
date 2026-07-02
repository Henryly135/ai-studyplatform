from __future__ import annotations

from collections import defaultdict
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.uuid_codec import encode_course_uuid, encode_module_uuid
from app.models.course_enrollments import CourseEnrollment, EnrollmentStatus
from app.models.courses import Course, CourseStatus
from app.models.learning_paths import LearningPath
from app.models.module_progress import ModuleProgress, ProgressStatus
from app.models.modules import Module, ModuleStatus
from app.models.quizzes import Quiz, QuizStatus
from app.models.quiz_attempts import QuizAttempt
from app.schemas.learner_progress import (
    LearnerProgressActivityItem,
    LearnerProgressCourseItem,
    LearnerProgressNextModule,
    LearnerProgressOverviewResponse,
    LearnerProgressQuizSummary,
)
from app.services.module_unlocking_service import ModuleUnlockingService
from platform_common.errors import http_error, invalid_identity_response_error


class LearnerProgressService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.unlocking = ModuleUnlockingService(session)

    def get_overview(self, *, current_user: dict) -> LearnerProgressOverviewResponse:
        learner_id = self._require_learner_id(current_user)
        enrolled_rows = self._load_enrolled_course_rows(learner_id)
        course_ids = [course.course_id for _enrollment, course in enrolled_rows]
        modules_by_course = self._load_modules_by_course(course_ids)
        module_ids = [module.module_id for modules in modules_by_course.values() for module in modules]
        progress_by_module = self._load_progress_by_module(learner_id=learner_id, module_ids=module_ids)
        quizzes_by_module = self._load_quizzes_by_module(module_ids)
        attempts_by_quiz = self._load_attempts_by_quiz(
            learner_id=learner_id,
            quiz_ids=[quiz.quiz_id for quiz in quizzes_by_module.values()],
        )

        course_items: list[LearnerProgressCourseItem] = []
        recent_activity: list[LearnerProgressActivityItem] = []

        for enrollment, course in enrolled_rows:
            modules = modules_by_course.get(course.course_id, [])
            module_quizzes = [
                quizzes_by_module[module.module_id]
                for module in modules
                if module.module_id in quizzes_by_module
            ]
            quiz_summary = self._build_quiz_summary(module_quizzes, attempts_by_quiz)

            next_module = self._find_next_module(
                modules=modules,
                learner_id=learner_id,
                progress_by_module=progress_by_module,
            )
            course_item = LearnerProgressCourseItem(
                courseId=course.course_id,
                courseUuid=encode_course_uuid(course.course_id),
                title=course.title,
                courseCode=getattr(course, "course_code", None),
                category=course.category,
                enrollmentStatus=enrollment.enrollment_status.value,
                progressPercent=float(enrollment.progress_percent or 0),
                completedModuleCount=int(enrollment.completed_module_count or 0),
                totalModuleCount=int(enrollment.total_module_count or len(modules)),
                lastAccessedAt=enrollment.last_accessed_at,
                completedAt=enrollment.completed_at,
                nextModule=(
                    LearnerProgressNextModule(
                        moduleId=next_module.module_id,
                        moduleUuid=encode_module_uuid(next_module.module_id),
                        title=next_module.title,
                    )
                    if next_module is not None
                    else None
                ),
                quiz=quiz_summary,
            )
            course_items.append(course_item)
            recent_activity.extend(
                self._build_course_activity(
                    course=course,
                    modules=modules,
                    progress_by_module=progress_by_module,
                    quizzes_by_module=quizzes_by_module,
                    attempts_by_quiz=attempts_by_quiz,
                )
            )

        recent_activity.sort(key=lambda item: item.occurredAt, reverse=True)
        total_modules = sum(course.totalModuleCount for course in course_items)
        completed_modules = sum(course.completedModuleCount for course in course_items)
        average_progress = mean([course.progressPercent for course in course_items]) if course_items else 0.0

        return LearnerProgressOverviewResponse(
            totalCourses=len(course_items),
            totalModules=total_modules,
            completedModules=completed_modules,
            averageProgressPercent=round(average_progress, 2),
            quiz=self._build_quiz_summary(list(quizzes_by_module.values()), attempts_by_quiz),
            courses=course_items,
            recentActivity=recent_activity[:8],
        )

    def _load_enrolled_course_rows(self, learner_id: int) -> list[tuple[CourseEnrollment, Course]]:
        stmt = (
            select(CourseEnrollment, Course)
            .join(Course, Course.course_id == CourseEnrollment.course_id)
            .where(
                CourseEnrollment.learner_id == learner_id,
                CourseEnrollment.enrollment_status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
                Course.status == CourseStatus.PUBLISHED,
            )
            .order_by(
                func.coalesce(CourseEnrollment.last_accessed_at, CourseEnrollment.enrolled_at).desc(),
                CourseEnrollment.enrolled_at.desc(),
                CourseEnrollment.enrollment_id.desc(),
            )
        )
        return [(enrollment, course) for enrollment, course in self.session.execute(stmt).all()]

    def _load_modules_by_course(self, course_ids: list[int]) -> dict[int, list[Module]]:
        if not course_ids:
            return {}
        stmt = (
            select(Course.course_id, Module)
            .join(LearningPath, LearningPath.course_id == Course.course_id)
            .join(Module, Module.learning_path_id == LearningPath.learning_path_id)
            .where(
                Course.course_id.in_(course_ids),
                Module.status == ModuleStatus.PUBLISHED,
            )
            .order_by(Course.course_id.asc(), Module.sort_order.asc(), Module.module_id.asc())
        )
        modules_by_course: dict[int, list[Module]] = defaultdict(list)
        for course_id, module in self.session.execute(stmt).all():
            modules_by_course[int(course_id)].append(module)
        return dict(modules_by_course)

    def _load_progress_by_module(self, *, learner_id: int, module_ids: list[int]) -> dict[int, ModuleProgress]:
        if not module_ids:
            return {}
        stmt = select(ModuleProgress).where(
            ModuleProgress.learner_id == learner_id,
            ModuleProgress.module_id.in_(module_ids),
        )
        return {progress.module_id: progress for progress in self.session.scalars(stmt)}

    def _load_quizzes_by_module(self, module_ids: list[int]) -> dict[int, Quiz]:
        if not module_ids:
            return {}
        stmt = select(Quiz).where(
            Quiz.module_id.in_(module_ids),
            Quiz.status == QuizStatus.PUBLISHED,
        )
        return {quiz.module_id: quiz for quiz in self.session.scalars(stmt)}

    def _load_attempts_by_quiz(self, *, learner_id: int, quiz_ids: list[int]) -> dict[int, list[QuizAttempt]]:
        if not quiz_ids:
            return {}
        stmt = (
            select(QuizAttempt)
            .where(
                QuizAttempt.learner_id == learner_id,
                QuizAttempt.quiz_id.in_(quiz_ids),
            )
            .order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.quiz_attempt_id.desc())
        )
        attempts_by_quiz: dict[int, list[QuizAttempt]] = defaultdict(list)
        for attempt in self.session.scalars(stmt):
            attempts_by_quiz[attempt.quiz_id].append(attempt)
        return dict(attempts_by_quiz)

    def _find_next_module(
        self,
        *,
        modules: list[Module],
        learner_id: int,
        progress_by_module: dict[int, ModuleProgress],
    ) -> Module | None:
        for module in modules:
            progress = progress_by_module.get(module.module_id)
            if progress is not None and progress.progress_status == ProgressStatus.COMPLETED:
                continue
            if self.unlocking.is_module_unlocked(module_id=module.module_id, learner_id=learner_id):
                return module
        return None

    def _build_quiz_summary(
        self,
        quizzes: list[Quiz],
        attempts_by_quiz: dict[int, list[QuizAttempt]],
    ) -> LearnerProgressQuizSummary:
        quiz_attempts = [attempt for quiz in quizzes for attempt in attempts_by_quiz.get(quiz.quiz_id, [])]
        latest_attempt = max(quiz_attempts, key=lambda attempt: attempt.submitted_at) if quiz_attempts else None
        best_scores = [
            max(float(attempt.score_percent) for attempt in attempts)
            for quiz in quizzes
            if (attempts := attempts_by_quiz.get(quiz.quiz_id, []))
        ]
        return LearnerProgressQuizSummary(
            totalQuizzes=len(quizzes),
            attemptedQuizzes=sum(1 for quiz in quizzes if attempts_by_quiz.get(quiz.quiz_id)),
            passedQuizzes=sum(
                1
                for quiz in quizzes
                if any(attempt.is_passed for attempt in attempts_by_quiz.get(quiz.quiz_id, []))
            ),
            totalAttempts=len(quiz_attempts),
            averageBestScorePercent=round(mean(best_scores), 2) if best_scores else None,
            latestScorePercent=float(latest_attempt.score_percent) if latest_attempt is not None else None,
            latestSubmittedAt=latest_attempt.submitted_at if latest_attempt is not None else None,
        )

    def _build_course_activity(
        self,
        *,
        course: Course,
        modules: list[Module],
        progress_by_module: dict[int, ModuleProgress],
        quizzes_by_module: dict[int, Quiz],
        attempts_by_quiz: dict[int, list[QuizAttempt]],
    ) -> list[LearnerProgressActivityItem]:
        activities: list[LearnerProgressActivityItem] = []
        course_uuid = encode_course_uuid(course.course_id)

        for module in modules:
            module_uuid = encode_module_uuid(module.module_id)
            progress = progress_by_module.get(module.module_id)
            if progress is not None and progress.completed_at is not None:
                activities.append(
                    LearnerProgressActivityItem(
                        activityType="module_completed",
                        occurredAt=progress.completed_at,
                        courseId=course.course_id,
                        courseUuid=course_uuid,
                        courseTitle=course.title,
                        moduleId=module.module_id,
                        moduleUuid=module_uuid,
                        moduleTitle=module.title,
                        title="Completed module",
                        detail=module.title,
                    )
                )
            elif progress is not None and progress.last_accessed_at is not None:
                activities.append(
                    LearnerProgressActivityItem(
                        activityType="module_accessed",
                        occurredAt=progress.last_accessed_at,
                        courseId=course.course_id,
                        courseUuid=course_uuid,
                        courseTitle=course.title,
                        moduleId=module.module_id,
                        moduleUuid=module_uuid,
                        moduleTitle=module.title,
                        title="Studied module",
                        detail=module.title,
                    )
                )

            quiz = quizzes_by_module.get(module.module_id)
            if quiz is None:
                continue
            for attempt in attempts_by_quiz.get(quiz.quiz_id, []):
                activities.append(
                    LearnerProgressActivityItem(
                        activityType="quiz_submitted",
                        occurredAt=attempt.submitted_at,
                        courseId=course.course_id,
                        courseUuid=course_uuid,
                        courseTitle=course.title,
                        moduleId=module.module_id,
                        moduleUuid=module_uuid,
                        moduleTitle=module.title,
                        title="Submitted quiz",
                        detail=f"{quiz.title} attempt {attempt.attempt_number}",
                        scorePercent=float(attempt.score_percent),
                        isPassed=attempt.is_passed,
                    )
                )
        return activities

    def _require_learner_id(self, current_user: dict) -> int:
        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise invalid_identity_response_error()
        if current_user.get("identity") != "Learner":
            raise http_error(status_code=403, code="LEARNER_ONLY", message="Only learners can view learning progress")
        return learner_id
