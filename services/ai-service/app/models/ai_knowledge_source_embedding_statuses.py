from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIKnowledgeSourceEmbeddingStatus(Base):
    """Tracks whether one source is fully indexed for one embedding model."""

    __tablename__ = "ai_knowledge_source_embedding_statuses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'success', 'failed')",
            name="ck_ai_source_embedding_status",
        ),
        CheckConstraint(
            "expected_chunk_count >= 0 "
            "AND indexed_chunk_count >= 0 "
            "AND indexed_chunk_count <= expected_chunk_count",
            name="ck_ai_source_embedding_chunk_counts",
        ),
        Index(
            "idx_ai_source_embedding_status_model_status",
            "embedding_model_id",
            "status",
        ),
    )

    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ai_knowledge_sources.source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding_model_id: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("ai_model_catalog.model_id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding_version: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    expected_chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    indexed_chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
