from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import enum_values


class AIIndexJobType(str, Enum):
    INDEX_MATERIAL = "index_material"
    REINDEX_MATERIAL = "reindex_material"
    DELETE_MATERIAL_INDEX = "delete_material_index"
    REINDEX_COURSE = "reindex_course"


class AIIndexSourceType(str, Enum):
    MATERIAL = "material"
    MODULE = "module"
    COURSE = "course"
    FAQ = "faq"


class AIJobStatus(str, Enum):
    BLOCKED = "blocked"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class AIIndexJob(Base):
    __tablename__ = "ai_index_jobs"

    job_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    job_type: Mapped[AIIndexJobType] = mapped_column(
        SqlEnum(AIIndexJobType, values_callable=enum_values, name="ai_index_job_type"),
        nullable=False,
    )
    source_type: Mapped[AIIndexSourceType] = mapped_column(
        SqlEnum(AIIndexSourceType, values_callable=enum_values, name="ai_index_source_type"),
        nullable=False,
    )
    source_ref_id: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger, 
        nullable=True
    )
    module_id: Mapped[int | None] = mapped_column(
        BigInteger, 
        nullable=True
    )
    material_id: Mapped[int | None] = mapped_column(
        BigInteger, 
        nullable=True
    )
    source_version: Mapped[str | None] = mapped_column(
        String(500), 
        nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(128), 
        nullable=True
    )
    status: Mapped[AIJobStatus] = mapped_column(
        SqlEnum(AIJobStatus, values_callable=enum_values, name="ai_job_status"),
        nullable=False,
        default=AIJobStatus.QUEUED,
        server_default=AIJobStatus.QUEUED.value,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default="100",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    metadata_json: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    trigger_event_id: Mapped[str | None] = mapped_column(
        String(100), 
        nullable=True
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(100), 
        nullable=True
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
