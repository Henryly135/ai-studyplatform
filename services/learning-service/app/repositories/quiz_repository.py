from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quizzes import Quiz, QuizStatus

_UNSET = object()


class QuizRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, quiz_id: int) -> Quiz | None:
        return self.session.get(Quiz, quiz_id)

    def get_by_module_id(self, module_id: int) -> Quiz | None:
        stmt = select(Quiz).where(Quiz.module_id == module_id)
        return self.session.scalar(stmt)

    def create(
        self,
        *,
        module_id: int,
        title: str,
        description: str | None,
        status: QuizStatus,
        time_limit_seconds: int | None,
        question_count_per_attempt: int,
        shuffle_questions: bool,
        shuffle_options: bool,
        published_at: datetime | None = None,
    ) -> Quiz:
        quiz = Quiz(
            module_id=module_id,
            title=title,
            description=description,
            status=status,
            time_limit_seconds=time_limit_seconds,
            question_count_per_attempt=question_count_per_attempt,
            shuffle_questions=shuffle_questions,
            shuffle_options=shuffle_options,
            published_at=published_at,
        )
        self.session.add(quiz)
        self.session.flush()
        return quiz

    def update(
        self,
        quiz: Quiz,
        *,
        title: str | object = _UNSET,
        description: str | None | object = _UNSET,
        status: QuizStatus | object = _UNSET,
        time_limit_seconds: int | None | object = _UNSET,
        question_count_per_attempt: int | object = _UNSET,
        shuffle_questions: bool | object = _UNSET,
        shuffle_options: bool | object = _UNSET,
        published_at: datetime | None | object = _UNSET,
    ) -> Quiz:
        if title is not _UNSET:
            quiz.title = title
        if description is not _UNSET:
            quiz.description = description
        if status is not _UNSET:
            quiz.status = status
        if time_limit_seconds is not _UNSET:
            quiz.time_limit_seconds = time_limit_seconds
        if question_count_per_attempt is not _UNSET:
            quiz.question_count_per_attempt = question_count_per_attempt
        if shuffle_questions is not _UNSET:
            quiz.shuffle_questions = shuffle_questions
        if shuffle_options is not _UNSET:
            quiz.shuffle_options = shuffle_options
        if published_at is not _UNSET:
            quiz.published_at = published_at
        self.session.flush()
        return quiz

    def delete(self, quiz: Quiz) -> None:
        self.session.delete(quiz)
        self.session.flush()
