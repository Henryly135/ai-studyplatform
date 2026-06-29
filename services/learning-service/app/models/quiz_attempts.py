from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DECIMAL, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint(
            "quiz_id",
            "learner_id",
            "attempt_number",
            name="uq_quiz_attempts_quiz_learner_attempt_number",
        ),
    )

    quiz_attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    quiz_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quizzes.quiz_id", ondelete="CASCADE"),
        nullable=False,
    )
    module_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        nullable=False,
    )
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(nullable=False)
    question_count: Mapped[int] = mapped_column(nullable=False)
    correct_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    score_percent: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    is_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    is_timed_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    time_limit_seconds_snapshot: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    quiz = relationship(
        "Quiz",
        foreign_keys="QuizAttempt.quiz_id",
        back_populates="attempts",
    )
    module = relationship(
        "Module",
        foreign_keys="QuizAttempt.module_id",
    )
    answers = relationship(
        "QuizAttemptAnswer",
        foreign_keys="QuizAttemptAnswer.quiz_attempt_id",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )
