from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, JSON, ForeignKey, DateTime, Enum as SqlEnum, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values

class MaterialType(str, Enum):
    PDF = "pdf"
    VIDEO = "video"
    FILE = "file"
    LINK = "link"
    TEXT = "text"

class ModuleMaterial(Base):
    __tablename__ = "module_materials"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "sort_order",
            name="uq_module_materials_module_sort_order",
        ),
    )

    # mapped_column maps each Python attribute to a concrete column
    material_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True, 
        autoincrement=True
    )
    module_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(200), 
        nullable=False
    )
    material_type: Mapped[MaterialType] = mapped_column(
        SqlEnum(MaterialType, values_callable=enum_values),
        nullable=False
    )
    resource_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        nullable=False
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
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
    module = relationship(
        "Module",
        foreign_keys="ModuleMaterial.module_id",
        back_populates="materials",
    )
