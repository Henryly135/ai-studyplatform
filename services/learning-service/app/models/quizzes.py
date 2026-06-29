from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class QuizStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class QuizPassingRule(str, Enum):
    ALL_CORRECT = "all_correct"


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            name="uq_quizzes_module_id",
        ),
    )

    quiz_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    module_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[QuizStatus] = mapped_column(
        SqlEnum(QuizStatus, values_callable=enum_values),
        nullable=False,
        default=QuizStatus.DRAFT,
        server_default=QuizStatus.DRAFT.value,
    )
    time_limit_seconds: Mapped[int | None] = mapped_column(nullable=True)
    question_count_per_attempt: Mapped[int] = mapped_column(nullable=False)
    shuffle_questions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    shuffle_options: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    passing_rule: Mapped[QuizPassingRule] = mapped_column(
        SqlEnum(QuizPassingRule, values_callable=enum_values),
        nullable=False,
        default=QuizPassingRule.ALL_CORRECT,
        server_default=QuizPassingRule.ALL_CORRECT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
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

    module = relationship(
        "Module",
        foreign_keys="Quiz.module_id",
        back_populates="quiz",
    )
    questions = relationship(
        "QuizQuestion",
        foreign_keys="QuizQuestion.quiz_id",
        back_populates="quiz",
        cascade="all, delete-orphan",
    )
    attempts = relationship(
        "QuizAttempt",
        foreign_keys="QuizAttempt.quiz_id",
        back_populates="quiz",
        cascade="all, delete-orphan",
    )
