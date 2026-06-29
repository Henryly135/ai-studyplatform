from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# These token models are used for account verification and password recovery flows.
# They are not login session tokens such as JWT access tokens or refresh tokens.
class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    # mapped_column maps each Python attribute to a concrete column in the users table.
    token_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # relationship declares ORM links to related tables 
    user = relationship(
        "User", 
        back_populates="email_verification_tokens"
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    token_id: Mapped[int] = mapped_column(
        primary_key=True, 
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), 
        nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # Relationships
    user = relationship(
        "User", 
        back_populates="password_reset_tokens"
    )
