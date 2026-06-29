from datetime import datetime
from enum import Enum
from decimal import Decimal

from sqlalchemy import BigInteger, DECIMAL, ForeignKey, DateTime, Enum as SqlEnum, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values

class EnrollmentStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"

class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "learner_id",
            name="uq_course_enrollments_course_learner",
        ),
    )

    # Relationships
    enrollment_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True, 
        autoincrement=True
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.course_id", ondelete="CASCADE"),
        nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    enrollment_status: Mapped[EnrollmentStatus] = mapped_column(
        SqlEnum(EnrollmentStatus, values_callable=enum_values),
        nullable=False,
        default=EnrollmentStatus.ACTIVE,
        server_default=EnrollmentStatus.ACTIVE.value,
    )
    progress_percent: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    completed_module_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    total_module_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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
        foreign_keys="CourseEnrollment.course_id",
        back_populates="enrollments",
    )
    audit_logs = relationship(
        "CourseEnrollmentAuditLog",
        foreign_keys="CourseEnrollmentAuditLog.enrollment_id",
        back_populates="enrollment",
        cascade="all, delete-orphan",
    )
