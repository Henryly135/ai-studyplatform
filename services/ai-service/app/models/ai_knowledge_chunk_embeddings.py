from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


MULTI_EMBEDDING_DIMENSION = 1024


class AIKnowledgeChunkEmbedding(Base):
    """Provider-specific vector for one canonical knowledge chunk."""

    __tablename__ = "ai_knowledge_chunk_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "embedding_model_id",
            name="uq_ai_chunk_embeddings_chunk_model",
        ),
        CheckConstraint(
            "embedding_dimension = 1024",
            name="ck_ai_chunk_embeddings_dimension",
        ),
        Index(
            "idx_ai_chunk_embeddings_model_id",
            "embedding_model_id",
        ),
    )

    chunk_embedding_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    chunk_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ai_knowledge_chunks.chunk_id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding_model_id: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("ai_model_catalog.model_id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding_version: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=MULTI_EMBEDDING_DIMENSION,
        server_default=str(MULTI_EMBEDDING_DIMENSION),
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(MULTI_EMBEDDING_DIMENSION),
        nullable=False,
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
