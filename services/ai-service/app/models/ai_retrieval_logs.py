from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIRetrievalLog(Base):
    __tablename__ = "ai_retrieval_logs"

    retrieval_id: Mapped[int] = mapped_column(
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
    retrieval_mode: Mapped[str | None] = mapped_column(
        String(50), 
        nullable=True
    )
    user_query: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    rewritten_query: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    query_embedding_model: Mapped[str | None] = mapped_column(
        String(100), 
        nullable=True
    )
    filters_json: Mapped[dict | list | None] = mapped_column(
        JSONB, 
        nullable=True
    )
    top_k: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default="5",
    )
    results_json: Mapped[dict | list] = mapped_column(
        JSONB, 
        nullable=False
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer, 
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
        back_populates="retrieval_logs"
    )
    message = relationship(
        "AIChatMessage", 
        back_populates="retrieval_logs"
    )
