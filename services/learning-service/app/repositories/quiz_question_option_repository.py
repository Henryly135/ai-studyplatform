from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.quiz_question_options import QuizQuestionOption


class QuizQuestionOptionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_question(self, question_id: int) -> list[QuizQuestionOption]:
        stmt = (
            select(QuizQuestionOption)
            .where(QuizQuestionOption.quiz_question_id == question_id)
            .order_by(QuizQuestionOption.sort_order.asc(), QuizQuestionOption.quiz_question_option_id.asc())
        )
        return list(self.session.scalars(stmt))

    def get_by_id(self, option_id: int) -> QuizQuestionOption | None:
        return self.session.get(QuizQuestionOption, option_id)

    def create(
        self,
        *,
        quiz_question_id: int,
        option_label: str | None,
        option_text: str,
        sort_order: int,
        is_correct: bool,
    ) -> QuizQuestionOption:
        option = QuizQuestionOption(
            quiz_question_id=quiz_question_id,
            option_label=option_label,
            option_text=option_text,
            sort_order=sort_order,
            is_correct=is_correct,
        )
        self.session.add(option)
        self.session.flush()
        return option

    def delete_by_question(self, question_id: int) -> None:
        self.session.execute(
            delete(QuizQuestionOption).where(QuizQuestionOption.quiz_question_id == question_id)
        )
        self.session.flush()
