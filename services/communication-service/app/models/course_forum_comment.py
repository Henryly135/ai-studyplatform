from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import enum_values


class ForumCommentKind(str, Enum):
    USER = "user"
    SYSTEM = "system"


class CourseForumComment(Base):
    __tablename__ = "course_forum_comments"

    comment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("course_forum_posts.post_id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_email: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    root_comment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("course_forum_comments.comment_id", ondelete="CASCADE"),
        nullable=True,
    )
    reply_to_comment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("course_forum_comments.comment_id", ondelete="SET NULL"),
        nullable=True,
    )
    comment_kind: Mapped[ForumCommentKind] = mapped_column(
        SqlEnum(ForumCommentKind, values_callable=enum_values),
        nullable=False,
        default=ForumCommentKind.USER,
        server_default=ForumCommentKind.USER.value,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
