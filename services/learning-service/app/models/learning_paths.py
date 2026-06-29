from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class LearningPath(Base):
    __tablename__ = "learning_paths"

    # mapped_column maps each Python attribute to a concrete column
    learning_path_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True, 
        autoincrement=True
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.course_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Enforce one-to-one relationship with Course
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text,
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
    course = relationship(
        "Course",
        foreign_keys="LearningPath.course_id",
        back_populates="learning_path",
    )
    modules = relationship(
        "Module",
        foreign_keys="Module.learning_path_id",
        back_populates="learning_path",
        cascade="all, delete-orphan",
    )
