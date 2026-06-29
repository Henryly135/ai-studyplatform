from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class ShortAnswerSubmissionStatus(str, Enum):
    SUBMITTED = "submitted"
    AI_SUGGESTED = "ai_suggested"
    REVIEWED = "reviewed"


class ShortAnswerSubmission(Base):
    __tablename__ = "short_answer_submissions"

    short_answer_submission_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    assessment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("short_answer_assessments.short_answer_assessment_id", ondelete="CASCADE"),
        nullable=False,
    )
    learner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_score_suggestion: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    ai_feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_strengths_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ai_improvements_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ai_provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_provider_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    final_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    final_feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[ShortAnswerSubmissionStatus] = mapped_column(
        SqlEnum(ShortAnswerSubmissionStatus, values_callable=enum_values),
        nullable=False,
        default=ShortAnswerSubmissionStatus.SUBMITTED,
        server_default=ShortAnswerSubmissionStatus.SUBMITTED.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    assessment = relationship(
        "ShortAnswerAssessment",
        foreign_keys="ShortAnswerSubmission.assessment_id",
        back_populates="submissions",
    )
