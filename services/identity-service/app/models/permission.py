from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Permission(Base):
    __tablename__ = "permissions"

    # mapped_column maps each Python attribute to a concrete column in the users table.
    permission_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True
    )
    permission_code: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        nullable=False)
    permission_name: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        String(255), 
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # Relationships
    role_permissions = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )
