from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CourseInviteToken(Base):
    __tablename__ = "course_invite_tokens"

    invite_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invite_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    token_hash: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    course = relationship("Course", foreign_keys=[course_id])
