from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import enum_values


class StudyPlanStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class StudyPlan(Base):
    __tablename__ = "study_plans"

    plan_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    learner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[StudyPlanStatus] = mapped_column(
        SqlEnum(StudyPlanStatus, values_callable=enum_values),
        nullable=False,
        default=StudyPlanStatus.ACTIVE,
        server_default=StudyPlanStatus.ACTIVE.value,
    )
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    fallback_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    adjustment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
