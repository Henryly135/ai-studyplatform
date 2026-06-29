from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class ChangeType(str, Enum):
    ROLE_CHANGE = "role_change"
    STATUS_CHANGE = "status_change"
    APPROVAL_RESULT = "approval_result"


class AuditAccountStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    DEACTIVATED = "deactivated"


class LoginResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class UserRoleAuditLog(Base):
    __tablename__ = "user_role_audit_logs"

    audit_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True
    )
    target_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), 
        nullable=False
    )
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    change_type: Mapped[ChangeType] = mapped_column(
        SqlEnum(ChangeType, values_callable=enum_values),
        nullable=False,
    )
    old_role_id: Mapped[int | None] = mapped_column(
        ForeignKey("roles.role_id", ondelete="SET NULL")
    )
    new_role_id: Mapped[int | None] = mapped_column(
        ForeignKey("roles.role_id", ondelete="SET NULL")
    )
    old_status: Mapped[AuditAccountStatus | None] = mapped_column(
        SqlEnum(AuditAccountStatus, values_callable=enum_values)
    )
    new_status: Mapped[AuditAccountStatus | None] = mapped_column(
        SqlEnum(AuditAccountStatus, values_callable=enum_values)
    )
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    target_user = relationship(
        "User",
        foreign_keys=[target_user_id],
        back_populates="target_user_role_audit_logs",
    )
    changed_by_user = relationship(
        "User",
        foreign_keys=[changed_by],
        back_populates="changed_user_role_audit_logs",
    )
    old_role = relationship(
        "Role", 
        foreign_keys=[old_role_id], 
        back_populates="old_user_role_audit_logs"
    )
    new_role = relationship(
        "Role", 
        foreign_keys=[new_role_id], 
        back_populates="new_user_role_audit_logs"
    )


class LoginAuditLog(Base):
    __tablename__ = "login_audit_logs"

    log_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    email_attempted: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    login_result: Mapped[LoginResult] = mapped_column(
        SqlEnum(LoginResult, values_callable=enum_values),
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # Relationships
    user = relationship(
        "User", 
        back_populates="login_audit_logs"
    )
