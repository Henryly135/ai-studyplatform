from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import enum_values


class ForumPostKind(str, Enum):
    USER = "user"
    SYSTEM = "system"


class CourseForumPost(Base):
    __tablename__ = "course_forum_posts"

    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    author_email: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    post_kind: Mapped[ForumPostKind] = mapped_column(
        SqlEnum(ForumPostKind, values_callable=enum_values),
        nullable=False,
        default=ForumPostKind.USER,
        server_default=ForumPostKind.USER.value,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pinned_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
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
