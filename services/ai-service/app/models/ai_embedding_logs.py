from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.ai_prompt_logs import AIPromptStatus
from app.models.common import enum_values


class AIEmbeddingLog(Base):
    __tablename__ = "ai_embedding_logs"

    embedding_log_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    job_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ai_index_jobs.job_id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    module_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    material_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    chunk_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    chunk_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    task_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    input_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    input_chars: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    provider_input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    provider_total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    vector_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    output_dimensionality: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    request_json: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    response_json: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    status: Mapped[AIPromptStatus] = mapped_column(
        SqlEnum(AIPromptStatus, values_callable=enum_values, name="ai_prompt_status"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
