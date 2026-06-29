from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class AIFeedbackType(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    REPORT = "report"


class AIFeedback(Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "user_id",
            "feedback_type",
            name="uq_ai_feedback_message_user_type",
        ),
    )

    feedback_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ai_chat_messages.message_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, 
        nullable=False
    )
    feedback_type: Mapped[AIFeedbackType] = mapped_column(
        SqlEnum(AIFeedbackType, values_callable=enum_values, name="ai_feedback_type"),
        nullable=False,
    )
    comment_text: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )


    # Realtionships
    message = relationship("AIChatMessage", back_populates="feedback_items")
