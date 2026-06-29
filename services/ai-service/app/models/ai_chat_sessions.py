from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class AISessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, 
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
    session_type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )
    title: Mapped[str | None] = mapped_column(
        String(255), 
        nullable=True
    )
    status: Mapped[AISessionStatus] = mapped_column(
        SqlEnum(AISessionStatus, values_callable=enum_values, name="ai_session_status"),
        nullable=False,
        default=AISessionStatus.ACTIVE,
        server_default=AISessionStatus.ACTIVE.value,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
    last_user_message_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
    last_assistant_message_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    summary_text: Mapped[str | None] = mapped_column(
        Text, 
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
    messages = relationship(
        "AIChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    prompt_logs = relationship(
        "AIPromptLog", 
        back_populates="session"
    )
    retrieval_logs = relationship(
        "AIRetrievalLog", 
        back_populates="session"
    )
