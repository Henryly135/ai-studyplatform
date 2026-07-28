from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.ai_knowledge_sources import AIPublishStatus, AIVisibilityScope
from app.models.common import enum_values
from sqlalchemy import Enum as SqlEnum


class AIKnowledgeChunk(Base):
    __tablename__ = "ai_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "chunk_index",
            name="uq_ai_knowledge_chunks_source_index",
        ),
    )

    chunk_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ai_knowledge_sources.source_id", ondelete="CASCADE"),
        nullable=False,
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
    chunk_index: Mapped[int] = mapped_column(
        Integer, 
        nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    heading_path: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    start_char: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    end_char: Mapped[int | None] = mapped_column(
        Integer, 
        nullable=True
    )
    chunk_hash: Mapped[str] = mapped_column(
        String(128), 
        nullable=False
    )
    language_code: Mapped[str | None] = mapped_column(
        String(20), 
        nullable=True
    )
    visibility_scope: Mapped[AIVisibilityScope] = mapped_column(
        SqlEnum(AIVisibilityScope, values_callable=enum_values, name="ai_visibility_scope"),
        nullable=False,
        default=AIVisibilityScope.COURSE_ONLY,
        server_default=AIVisibilityScope.COURSE_ONLY.value,
    )
    publish_status: Mapped[AIPublishStatus] = mapped_column(
        SqlEnum(AIPublishStatus, values_callable=enum_values, name="ai_publish_status"),
        nullable=False,
        default=AIPublishStatus.PUBLISHED,
        server_default=AIPublishStatus.PUBLISHED.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    # Legacy single-vector fields are kept nullable during the multi-vector
    # migration so an existing deployment can roll back without losing data.
    embedding_model: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    embedding_version: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(),
        nullable=True,
    )
    metadata_json: Mapped[dict | list | None] = mapped_column(
        JSONB, 
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )


    # Relationships
    source = relationship("AIKnowledgeSource", back_populates="chunks")
