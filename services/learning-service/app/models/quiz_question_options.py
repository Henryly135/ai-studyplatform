from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuizQuestionOption(Base):
    __tablename__ = "quiz_question_options"
    __table_args__ = (
        UniqueConstraint(
            "quiz_question_id",
            "sort_order",
            name="uq_quiz_question_options_question_sort_order",
        ),
    )

    quiz_question_option_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    quiz_question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quiz_questions.quiz_question_id", ondelete="CASCADE"),
        nullable=False,
    )
    option_label: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    option_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    question = relationship(
        "QuizQuestion",
        foreign_keys="QuizQuestionOption.quiz_question_id",
        back_populates="options",
    )
    selected_attempt_answers = relationship(
        "QuizAttemptAnswer",
        foreign_keys="QuizAttemptAnswer.selected_option_id",
        back_populates="selected_option",
    )
