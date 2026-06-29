from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class EnrollmentAuditActionType(str, Enum):
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    RE_ENROLLED = "re_enrolled"
    COMPLETED = "completed"
    STATUS_CHANGED = "status_changed"


class EnrollmentAuditActorRole(str, Enum):
    LEARNER = "learner"
    EDUCATOR = "educator"
    ADMIN = "admin"
    SYSTEM = "system"


class CourseEnrollmentAuditLog(Base):
    __tablename__ = "course_enrollment_audit_logs"

    audit_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    enrollment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("course_enrollments.enrollment_id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.course_id", ondelete="CASCADE"),
        nullable=False,
    )
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    action_type: Mapped[EnrollmentAuditActionType] = mapped_column(
        SqlEnum(EnrollmentAuditActionType, values_callable=enum_values),
        nullable=False,
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    changed_by_role: Mapped[EnrollmentAuditActorRole] = mapped_column(
        SqlEnum(EnrollmentAuditActorRole, values_callable=enum_values),
        nullable=False,
    )
    old_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    new_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    enrollment = relationship(
        "CourseEnrollment",
        foreign_keys="CourseEnrollmentAuditLog.enrollment_id",
        back_populates="audit_logs",
    )
    course = relationship(
        "Course",
        foreign_keys="CourseEnrollmentAuditLog.course_id",
        back_populates="enrollment_audit_logs",
    )
