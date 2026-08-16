from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import enum_values


class AIProfileAssetStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class LearnerGlobalProfileAsset(Base):
    __tablename__ = "learner_global_profile_assets"

    profile_asset_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    preferences: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[AIProfileAssetStatus] = mapped_column(
        SqlEnum(AIProfileAssetStatus, values_callable=enum_values, name="ai_profile_asset_status"),
        nullable=False,
        default=AIProfileAssetStatus.ACTIVE,
        server_default=AIProfileAssetStatus.ACTIVE.value,
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
