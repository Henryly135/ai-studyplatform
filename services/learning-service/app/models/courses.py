from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class CourseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DifficultyLevelStatus(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    # Logical foreign key to identity-service users.user_id.
    educator_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    subtitle: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    cover_image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    status: Mapped[CourseStatus] = mapped_column(
        SqlEnum(CourseStatus, values_callable=enum_values),
        nullable=False,
        default=CourseStatus.DRAFT,
        server_default=CourseStatus.DRAFT.value,
    )
    difficulty_level: Mapped[DifficultyLevelStatus | None] = mapped_column(
        SqlEnum(DifficultyLevelStatus, values_callable=enum_values),
        nullable=True,
    )
    estimated_minutes: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    language_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
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
    learning_path = relationship(
        "LearningPath",
        foreign_keys="LearningPath.course_id",
        back_populates="course",
        cascade="all, delete-orphan",
        uselist=False,
    )
    enrollments = relationship(
        "CourseEnrollment",
        foreign_keys="CourseEnrollment.course_id",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    enrollment_audit_logs = relationship(
        "CourseEnrollmentAuditLog",
        foreign_keys="CourseEnrollmentAuditLog.course_id",
        back_populates="course",
        cascade="all, delete-orphan",
    )
