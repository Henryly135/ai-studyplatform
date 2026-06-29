from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class AIPromptCallType(str, Enum):
    CHAT = "chat"
    RETRIEVAL = "retrieval"
    QUERY_REWRITE = "query_rewrite"
    SUMMARIZATION = "summarization"
    EMBEDDING = "embedding"
    INDEXING_SYSTEM = "indexing_system"


class AIPromptStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AIPromptLog(Base):
    __tablename__ = "ai_prompt_logs"

    prompt_log_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ai_chat_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ai_chat_messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, 
        nullable=False
    )
    call_type: Mapped[AIPromptCallType] = mapped_column(
        SqlEnum(AIPromptCallType, values_callable=enum_values, name="ai_prompt_call_type"),
        nullable=False,
    )
    prompt_template_name: Mapped[str | None] = mapped_column(
        String(100), 
        nullable=True
    )
    model_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    input_text: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    output_text: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    request_json: Mapped[dict | list | None] = mapped_column(
        JSONB, 
        nullable=True
    )
    response_json: Mapped[dict | list | None] = mapped_column(
        JSONB, 
        nullable=True
    )
    prompt_tokens: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    completion_tokens: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    total_tokens: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    status: Mapped[AIPromptStatus] = mapped_column(
        SqlEnum(AIPromptStatus, values_callable=enum_values, name="ai_prompt_status"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(100), 
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )


    # Relationships
    session = relationship(
        "AIChatSession", 
        back_populates="prompt_logs"
    )
    message = relationship(
        "AIChatMessage", 
        back_populates="prompt_logs"
    )
