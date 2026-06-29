from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuizAttemptAnswer(Base):
    __tablename__ = "quiz_attempt_answers"
    __table_args__ = (
        UniqueConstraint(
            "quiz_attempt_id",
            "quiz_question_id",
            name="uq_quiz_attempt_answers_attempt_question",
        ),
        UniqueConstraint(
            "quiz_attempt_id",
            "question_order",
            name="uq_quiz_attempt_answers_attempt_order",
        ),
    )

    quiz_attempt_answer_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    quiz_attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quiz_attempts.quiz_attempt_id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quiz_questions.quiz_question_id", ondelete="RESTRICT"),
        nullable=False,
    )
    selected_option_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("quiz_question_options.quiz_question_option_id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    question_order: Mapped[int] = mapped_column(nullable=False)
    question_text_snapshot: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    explanation_text_snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    selected_option_text_snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    correct_option_id_snapshot: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    correct_option_text_snapshot: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    option_order_snapshot_json: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
    )
    option_texts_snapshot_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    attempt = relationship(
        "QuizAttempt",
        foreign_keys="QuizAttemptAnswer.quiz_attempt_id",
        back_populates="answers",
    )
    question = relationship(
        "QuizQuestion",
        foreign_keys="QuizAttemptAnswer.quiz_question_id",
        back_populates="attempt_answers",
    )
    selected_option = relationship(
        "QuizQuestionOption",
        foreign_keys="QuizAttemptAnswer.selected_option_id",
        back_populates="selected_attempt_answers",
    )
