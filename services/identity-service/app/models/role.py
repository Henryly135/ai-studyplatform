from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    # mapped_column maps each Python attribute to a concrete column in the users table.
    role_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True
    )
    role_code: Mapped[str] = mapped_column(
        String(50), 
        unique=True, 
        nullable=False
    )
    role_name: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        String(255)
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
    user_roles = relationship(
        "UserRole", 
        back_populates="role", 
        cascade="all, delete-orphan"
    )
    role_permissions = relationship(
        "RolePermission", 
        back_populates="role", 
        cascade="all, delete-orphan"
    )
    old_user_role_audit_logs = relationship(
        "UserRoleAuditLog",
        foreign_keys="UserRoleAuditLog.old_role_id",
        back_populates="old_role",
    )
    new_user_role_audit_logs = relationship(
        "UserRoleAuditLog",
        foreign_keys="UserRoleAuditLog.new_role_id",
        back_populates="new_role",
    )
