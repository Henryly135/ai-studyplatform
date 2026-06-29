from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.courses import Course
from app.models.learning_paths import LearningPath
from app.models.modules import Module
from app.models.quizzes import Quiz
from app.models.quiz_attempts import QuizAttempt


class QuizAttemptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, quiz_attempt_id: int) -> QuizAttempt | None:
        return self.session.get(QuizAttempt, quiz_attempt_id)

    def list_by_quiz_and_learner(self, *, quiz_id: int, learner_id: int) -> list[QuizAttempt]:
        stmt = (
            select(QuizAttempt)
            .where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.learner_id == learner_id,
            )
            .order_by(QuizAttempt.attempt_number.desc(), QuizAttempt.quiz_attempt_id.desc())
        )
        return list(self.session.scalars(stmt))

    def has_passed_quiz(self, *, quiz_id: int, learner_id: int) -> bool:
        stmt = select(func.count()).select_from(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.learner_id == learner_id,
            QuizAttempt.is_passed.is_(True),
        )
        return (self.session.scalar(stmt) or 0) > 0

    def get_max_attempt_number(self, *, quiz_id: int, learner_id: int) -> int:
        stmt = select(func.max(QuizAttempt.attempt_number)).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.learner_id == learner_id,
        )
        return self.session.scalar(stmt) or 0

    def count_by_quiz(self, *, quiz_id: int) -> int:
        stmt = select(func.count()).select_from(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id)
        return self.session.scalar(stmt) or 0

    def aggregate_stats_by_educator(self, *, educator_id: int) -> list[dict]:
        """Used by educator analytics to get per-module quiz stats across all courses owned by an educator."""
        stmt = (
            select(
                Course.course_id,
                Course.title.label("course_title"),
                Module.module_id,
                Module.title.label("module_title"),
                Module.sort_order,
                Quiz.title.label("quiz_title"),
                func.count(QuizAttempt.quiz_attempt_id).label("total_attempts"),
                func.count(func.distinct(QuizAttempt.learner_id)).label("unique_learners"),
                func.avg(QuizAttempt.score_percent).label("avg_score_percent"),
                func.avg(
                    case((QuizAttempt.is_passed, 1.0), else_=0.0)
                ).label("pass_rate"),
                func.avg(QuizAttempt.duration_seconds).label("avg_duration_seconds"),
            )
            .select_from(Course)
            .join(LearningPath, LearningPath.course_id == Course.course_id)
            .join(Module, Module.learning_path_id == LearningPath.learning_path_id)
            .join(Quiz, Quiz.module_id == Module.module_id)
            .outerjoin(QuizAttempt, QuizAttempt.quiz_id == Quiz.quiz_id)
            .where(Course.educator_id == educator_id)
            .group_by(
                Course.course_id,
                Course.title,
                Module.module_id,
                Module.title,
                Module.sort_order,
                Quiz.quiz_id,
                Quiz.title,
            )
            .order_by(Course.course_id.desc(), Module.sort_order.asc(), Module.module_id.asc())
        )

        rows = self.session.execute(stmt).all()
        return [
            {
                "course_id": row.course_id,
                "course_title": row.course_title,
                "module_id": row.module_id,
                "module_title": row.module_title,
                "quiz_title": row.quiz_title,
                "total_attempts": row.total_attempts or 0,
                "unique_learners": row.unique_learners or 0,
                "avg_score_percent": float(row.avg_score_percent) if row.avg_score_percent is not None else None,
                "pass_rate": float(row.pass_rate) if row.pass_rate is not None else None,
                "avg_duration_seconds": float(row.avg_duration_seconds) if row.avg_duration_seconds is not None else None,
            }
            for row in rows
        ]

    def create(
        self,
        *,
        quiz_id: int,
        module_id: int,
        learner_id: int,
        attempt_number: int,
        question_count: int,
        correct_count: int,
        score_percent: Decimal,
        is_passed: bool,
        is_timed_out: bool,
        time_limit_seconds_snapshot: int | None,
        started_at: datetime,
        submitted_at: datetime,
        duration_seconds: int | None,
    ) -> QuizAttempt:
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            module_id=module_id,
            learner_id=learner_id,
            attempt_number=attempt_number,
            question_count=question_count,
            correct_count=correct_count,
            score_percent=score_percent,
            is_passed=is_passed,
            is_timed_out=is_timed_out,
            time_limit_seconds_snapshot=time_limit_seconds_snapshot,
            started_at=started_at,
            submitted_at=submitted_at,
            duration_seconds=duration_seconds,
        )
        self.session.add(attempt)
        self.session.flush()
        return attempt
