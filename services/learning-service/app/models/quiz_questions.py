from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint(
            "quiz_id",
            "sort_order",
            name="uq_quiz_questions_quiz_sort_order",
        ),
    )

    quiz_question_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    quiz_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quizzes.quiz_id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    explanation_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_grounding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
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

    quiz = relationship(
        "Quiz",
        foreign_keys="QuizQuestion.quiz_id",
        back_populates="questions",
    )
    options = relationship(
        "QuizQuestionOption",
        foreign_keys="QuizQuestionOption.quiz_question_id",
        back_populates="question",
        cascade="all, delete-orphan",
    )
    attempt_answers = relationship(
        "QuizAttemptAnswer",
        foreign_keys="QuizAttemptAnswer.quiz_question_id",
        back_populates="question",
    )
