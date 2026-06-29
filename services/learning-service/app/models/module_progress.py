from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import BigInteger, DECIMAL, ForeignKey, DateTime, Enum as SqlEnum, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class ProgressStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class ModuleProgress(Base):
    __tablename__ = "module_progress"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "learner_id",
            name="uq_module_progress_module_learner",
        ),
    )

    # mapped_column maps each Python attribute to a concrete column
    module_progress_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True, 
        autoincrement=True
    )
    module_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    progress_status: Mapped[ProgressStatus] = mapped_column(
        SqlEnum(ProgressStatus, values_callable=enum_values),
        nullable=False,
        default=ProgressStatus.NOT_STARTED,
        server_default=ProgressStatus.NOT_STARTED.value,
    )
    progress_percent: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    time_spent_seconds: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
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


    # Relationships
    module = relationship(
        "Module",
        foreign_keys="ModuleProgress.module_id",
        back_populates="progress_records",
    )
