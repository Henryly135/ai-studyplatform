from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.quiz_questions import QuizQuestion


class QuizQuestionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_quiz(self, quiz_id: int) -> list[QuizQuestion]:
        stmt = (
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz_id)
            .order_by(QuizQuestion.sort_order.asc(), QuizQuestion.quiz_question_id.asc())
        )
        return list(self.session.scalars(stmt))

    def list_by_quiz_page(
        self,
        quiz_id: int,
        *,
        page: int,
        page_size: int,
        query: str | None = None,
    ) -> tuple[list[QuizQuestion], int]:
        filters = [
            QuizQuestion.quiz_id == quiz_id,
            QuizQuestion.sort_order < 10_000_000,
        ]
        normalized_query = (query or "").strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            filters.append(
                or_(
                    QuizQuestion.question_text.ilike(pattern),
                    QuizQuestion.explanation_text.ilike(pattern),
                )
            )

        total_stmt = select(func.count()).select_from(QuizQuestion).where(*filters)
        total = int(self.session.scalar(total_stmt) or 0)
        stmt = (
            select(QuizQuestion)
            .where(*filters)
            .order_by(QuizQuestion.sort_order.asc(), QuizQuestion.quiz_question_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(stmt)), total

    def count_by_quiz(self, quiz_id: int, *, active_only: bool = False) -> int:
        filters = [
            QuizQuestion.quiz_id == quiz_id,
            QuizQuestion.sort_order < 10_000_000,
        ]
        if active_only:
            filters.append(QuizQuestion.is_active.is_(True))
        stmt = select(func.count()).select_from(QuizQuestion).where(*filters)
        return int(self.session.scalar(stmt) or 0)

    def list_active_by_quiz(self, quiz_id: int) -> list[QuizQuestion]:
        stmt = (
            select(QuizQuestion)
            .where(
                QuizQuestion.quiz_id == quiz_id,
                QuizQuestion.is_active.is_(True),
            )
            .order_by(QuizQuestion.sort_order.asc(), QuizQuestion.quiz_question_id.asc())
        )
        return list(self.session.scalars(stmt))

    def list_by_ids(self, question_ids: list[int]) -> list[QuizQuestion]:
        if not question_ids:
            return []
        stmt = select(QuizQuestion).where(QuizQuestion.quiz_question_id.in_(question_ids))
        return list(self.session.scalars(stmt))

    def get_by_id(self, question_id: int) -> QuizQuestion | None:
        return self.session.get(QuizQuestion, question_id)

    def create(
        self,
        *,
        quiz_id: int,
        question_text: str,
        explanation_text: str | None,
        sort_order: int,
        is_active: bool,
        source_grounding: str | None = None,
    ) -> QuizQuestion:
        question = QuizQuestion(
            quiz_id=quiz_id,
            question_text=question_text,
            explanation_text=explanation_text,
            source_grounding=source_grounding,
            sort_order=sort_order,
            is_active=is_active,
        )
        self.session.add(question)
        self.session.flush()
        return question

    def update(
        self,
        question: QuizQuestion,
        *,
        question_text: str | None = None,
        explanation_text: str | None = None,
        source_grounding: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
    ) -> QuizQuestion:
        if question_text is not None:
            question.question_text = question_text
        question.explanation_text = explanation_text
        question.source_grounding = source_grounding
        if sort_order is not None:
            question.sort_order = sort_order
        if is_active is not None:
            question.is_active = is_active
        self.session.flush()
        return question

    def delete_by_quiz(self, quiz_id: int) -> None:
        self.session.execute(delete(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id))
        self.session.flush()
