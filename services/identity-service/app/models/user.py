from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class AccountStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    DEACTIVATED = "deactivated"


class User(Base):
    __tablename__ = "users"

    # mapped_column maps each Python attribute to a concrete column in the users table.
    user_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True
    )
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        SqlEnum(AccountStatus, values_callable=enum_values),
        nullable=False,
        default=AccountStatus.PENDING,
        server_default=AccountStatus.PENDING.value,
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
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
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    # relationship declares ORM links to related tables; 
    # these links do not add columns to users itself.
    user_roles = relationship(
        "UserRole", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    educator_approval_requests = relationship(
        "EducatorApprovalRequest",
        foreign_keys="EducatorApprovalRequest.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reviewed_educator_approval_requests = relationship(
        "EducatorApprovalRequest",
        foreign_keys="EducatorApprovalRequest.reviewed_by",
        back_populates="reviewer",
    )
    email_verification_tokens = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    target_user_role_audit_logs = relationship(
        "UserRoleAuditLog",
        foreign_keys="UserRoleAuditLog.target_user_id",
        back_populates="target_user",
        cascade="all, delete-orphan",
    )
    changed_user_role_audit_logs = relationship(
        "UserRoleAuditLog",
        foreign_keys="UserRoleAuditLog.changed_by",
        back_populates="changed_by_user",
    )
    login_audit_logs = relationship(
        "LoginAuditLog", 
        back_populates="user"
    )
