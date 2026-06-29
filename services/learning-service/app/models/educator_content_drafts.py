from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class EducatorContentDraftType(str, Enum):
    SUMMARY = "summary"
    LEARNING_OBJECTIVES = "learning_objectives"
    ACTIVITY_SUGGESTIONS = "activity_suggestions"
    DIFFERENTIATED_EXPLANATION = "differentiated_explanation"
    SLIDE_OUTLINE = "slide_outline"


class EducatorContentDraft(Base):
    __tablename__ = "educator_content_drafts"

    content_draft_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("modules.module_id", ondelete="CASCADE"), nullable=False)
    content_type: Mapped[EducatorContentDraftType] = mapped_column(
        SqlEnum(EducatorContentDraftType, values_callable=enum_values),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    teacher_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    grounding_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    module = relationship("Module", foreign_keys="EducatorContentDraft.module_id", back_populates="content_drafts")
