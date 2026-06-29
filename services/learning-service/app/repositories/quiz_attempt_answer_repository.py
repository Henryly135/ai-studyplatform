from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.quiz_attempt_answers import QuizAttemptAnswer


class QuizAttemptAnswerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_attempt(self, quiz_attempt_id: int) -> list[QuizAttemptAnswer]:
        stmt = (
            select(QuizAttemptAnswer)
            .where(QuizAttemptAnswer.quiz_attempt_id == quiz_attempt_id)
            .order_by(QuizAttemptAnswer.question_order.asc(), QuizAttemptAnswer.quiz_attempt_answer_id.asc())
        )
        return list(self.session.scalars(stmt))

    def count_by_question(self, quiz_question_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(QuizAttemptAnswer)
            .where(QuizAttemptAnswer.quiz_question_id == quiz_question_id)
        )
        return int(self.session.scalar(stmt) or 0)

    def create(
        self,
        *,
        quiz_attempt_id: int,
        quiz_question_id: int,
        selected_option_id: int | None,
        is_correct: bool,
        question_order: int,
        question_text_snapshot: str,
        explanation_text_snapshot: str | None,
        selected_option_text_snapshot: str | None,
        correct_option_id_snapshot: int,
        correct_option_text_snapshot: str,
        option_order_snapshot_json: list[int],
        option_texts_snapshot_json: list[dict[str, Any]],
    ) -> QuizAttemptAnswer:
        answer = QuizAttemptAnswer(
            quiz_attempt_id=quiz_attempt_id,
            quiz_question_id=quiz_question_id,
            selected_option_id=selected_option_id,
            is_correct=is_correct,
            question_order=question_order,
            question_text_snapshot=question_text_snapshot,
            explanation_text_snapshot=explanation_text_snapshot,
            selected_option_text_snapshot=selected_option_text_snapshot,
            correct_option_id_snapshot=correct_option_id_snapshot,
            correct_option_text_snapshot=correct_option_text_snapshot,
            option_order_snapshot_json=option_order_snapshot_json,
            option_texts_snapshot_json=option_texts_snapshot_json,
        )
        self.session.add(answer)
        self.session.flush()
        return answer
