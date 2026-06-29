from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class ShortAnswerAssessmentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ShortAnswerAssessment(Base):
    __tablename__ = "short_answer_assessments"
    __table_args__ = (
        UniqueConstraint("module_id", name="uq_short_answer_assessments_module"),
    )

    short_answer_assessment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assessment_uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    module_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("modules.module_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_text: Mapped[str] = mapped_column(Text, nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("10.00"))
    status: Mapped[ShortAnswerAssessmentStatus] = mapped_column(
        SqlEnum(ShortAnswerAssessmentStatus, values_callable=enum_values),
        nullable=False,
        default=ShortAnswerAssessmentStatus.DRAFT,
        server_default=ShortAnswerAssessmentStatus.DRAFT.value,
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    module = relationship("Module", foreign_keys="ShortAnswerAssessment.module_id", back_populates="short_answer_assessment")
    submissions = relationship(
        "ShortAnswerSubmission",
        foreign_keys="ShortAnswerSubmission.assessment_id",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
