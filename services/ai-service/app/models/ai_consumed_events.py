from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import enum_values


class AIEventStatus(str, Enum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class AIConsumedEvent(Base):
    __tablename__ = "ai_consumed_events"
    __table_args__ = (
        UniqueConstraint(
            "topic_name",
            "partition_id",
            "offset_value",
            name="uq_ai_consumed_events_topic_partition_offset",
        ),
    )

    event_id: Mapped[str] = mapped_column(
        String(100), 
        primary_key=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    topic_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    partition_id: Mapped[int] = mapped_column(
        Integer, 
        nullable=False
    )
    offset_value: Mapped[int] = mapped_column(
        BigInteger, 
        nullable=False
    )
    status: Mapped[AIEventStatus] = mapped_column(
        SqlEnum(AIEventStatus, values_callable=enum_values, name="ai_event_status"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
