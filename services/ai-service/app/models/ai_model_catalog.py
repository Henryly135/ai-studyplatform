from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIModelProvider(Base):
    __tablename__ = "ai_model_providers"

    provider_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    default_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backend_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    models = relationship("AIModelCatalog", back_populates="provider")
    credential = relationship("AIProviderCredential", back_populates="provider", uselist=False)


class AIModelCatalog(Base):
    __tablename__ = "ai_model_catalog"

    model_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    provider_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ai_model_providers.provider_key", ondelete="CASCADE"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    backend_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_chat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_json: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_embedding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_rag_answer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_rag_indexing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paired_embedding_model_id: Mapped[str | None] = mapped_column(
        String(120),
        ForeignKey("ai_model_catalog.model_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    unavailable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    provider = relationship("AIModelProvider", back_populates="models")

    __table_args__ = (
        UniqueConstraint("provider_key", "model_name", name="uq_ai_model_catalog_provider_model"),
    )


class AIProviderCredential(Base):
    __tablename__ = "ai_provider_credentials"

    provider_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ai_model_providers.provider_key", ondelete="CASCADE"),
        primary_key=True,
    )
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)
    base_url_override: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    health_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    provider = relationship("AIModelProvider", back_populates="credential")


class AIUserModelPreference(Base):
    __tablename__ = "ai_user_model_preferences"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_model_id: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("ai_model_catalog.model_id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class AIModelDefault(Base):
    __tablename__ = "ai_model_defaults"

    scope_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    default_chat_model_id: Mapped[str | None] = mapped_column(
        String(120),
        ForeignKey("ai_model_catalog.model_id", ondelete="SET NULL"),
        nullable=True,
    )
    default_embedding_model_id: Mapped[str | None] = mapped_column(
        String(120),
        ForeignKey("ai_model_catalog.model_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
