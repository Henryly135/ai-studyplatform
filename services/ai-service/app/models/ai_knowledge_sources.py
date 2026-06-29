from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class AIKnowledgeSourceType(str, Enum):
    MATERIAL = "material"
    MODULE_SUMMARY = "module_summary"
    COURSE_SUMMARY = "course_summary"
    FAQ = "faq"


class AIVisibilityScope(str, Enum):
    PUBLIC = "public"
    COURSE_ONLY = "course_only"
    PRIVATE = "private"


class AIPublishStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AIKnowledgeSource(Base):
    __tablename__ = "ai_knowledge_sources"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_ref_id",
            name="uq_ai_knowledge_sources_type_ref",
        ),
    )

    source_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    source_type: Mapped[AIKnowledgeSourceType] = mapped_column(
        SqlEnum(AIKnowledgeSourceType, values_callable=enum_values, name="ai_knowledge_source_type"),
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
    title: Mapped[str | None] = mapped_column(
        String(500), 
        nullable=True
    )
    content_text: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    content_markdown: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
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
    content_hash: Mapped[str] = mapped_column(
        String(128), 
        nullable=False
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(100), 
        nullable=True
    )
    embedding_version: Mapped[str | None] = mapped_column(
        String(50), 
        nullable=True
    )
    source_version: Mapped[str | None] = mapped_column(
        String(100), 
        nullable=True
    )
    metadata_json: Mapped[dict | list | None] = mapped_column(
        JSONB, 
        nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, 
        nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, 
        nullable=True
    )
    origin_event_id: Mapped[str | None] = mapped_column(
        String(100), 
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
    chunks = relationship(
        "AIKnowledgeChunk",
        back_populates="source",
        cascade="all, delete-orphan",
    )
