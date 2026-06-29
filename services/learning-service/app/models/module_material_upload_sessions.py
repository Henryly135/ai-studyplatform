from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Enum as SqlEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values
from app.models.module_materials import MaterialType


class MaterialUploadSessionStatus(str, Enum):
    INITIATED = "initiated"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class ModuleMaterialUploadSession(Base):
    __tablename__ = "module_material_upload_sessions"

    upload_session_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_uuid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    module_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    material_type: Mapped[MaterialType] = mapped_column(
        SqlEnum(MaterialType, values_callable=enum_values),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    bucket: Mapped[str | None] = mapped_column(String(100), nullable=True)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    multipart_upload_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MaterialUploadSessionStatus] = mapped_column(
        SqlEnum(MaterialUploadSessionStatus, values_callable=enum_values),
        nullable=False,
        default=MaterialUploadSessionStatus.INITIATED,
        server_default=MaterialUploadSessionStatus.INITIATED.value,
    )
    material_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("module_materials.material_id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
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

    module = relationship("Module", foreign_keys="ModuleMaterialUploadSession.module_id")
    material = relationship("ModuleMaterial", foreign_keys="ModuleMaterialUploadSession.material_id")
