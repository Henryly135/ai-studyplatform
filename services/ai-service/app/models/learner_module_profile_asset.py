from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.learner_global_profile_asset import AIProfileAssetStatus
from app.models.common import enum_values
from sqlalchemy import Enum as SqlEnum


class LearnerModuleProfileAsset(Base):
    __tablename__ = "learner_module_profile_assets"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "course_id",
            "module_id",
            "version",
            name="uq_learner_module_profile_assets_scope_version",
        ),
    )

    profile_asset_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    module_id: Mapped[int] = mapped_column(
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
