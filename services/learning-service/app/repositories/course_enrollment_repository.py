from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.course_enrollments import CourseEnrollment, EnrollmentStatus
from app.models.courses import Course

_UNSET = object()


class CourseEnrollmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, enrollment_id: int) -> CourseEnrollment | None:
        """Used by enrollment-detail services to load a course enrollment by primary key."""
        return self.session.get(CourseEnrollment, enrollment_id)

    def get_by_course_and_learner(
        self,
        course_id: int,
        learner_id: int,
    ) -> CourseEnrollment | None:
        """Used by enrollment services to resolve a learner's enrollment for a course."""
        stmt = select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.learner_id == learner_id,
        )
        return self.session.scalar(stmt)

    def list_by_course(self, course_id: int) -> list[CourseEnrollment]:
        """Used by educator analytics services to list enrollments for a course."""
        stmt = (
            select(CourseEnrollment)
            .where(CourseEnrollment.course_id == course_id)
            .order_by(CourseEnrollment.enrolled_at.desc(), CourseEnrollment.enrollment_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_current_by_course(self, course_id: int) -> list[CourseEnrollment]:
        """Used by course management services to list non-dropped learner enrollments for a course."""
        stmt = (
            select(CourseEnrollment)
            .where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.enrollment_status != EnrollmentStatus.DROPPED,
            )
            .order_by(CourseEnrollment.enrolled_at.desc(), CourseEnrollment.enrollment_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_learner(self, learner_id: int) -> list[CourseEnrollment]:
        """Used by learner dashboard services to list all course enrollments for a learner."""
        stmt = (
            select(CourseEnrollment)
            .where(CourseEnrollment.learner_id == learner_id)
            .order_by(CourseEnrollment.enrolled_at.desc(), CourseEnrollment.enrollment_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_active_by_learner(self, learner_id: int) -> list[CourseEnrollment]:
        """Used by learner home services to list a learner's active enrollments."""
        stmt = (
            select(CourseEnrollment)
            .where(
                CourseEnrollment.learner_id == learner_id,
                CourseEnrollment.enrollment_status == EnrollmentStatus.ACTIVE,
            )
            .order_by(CourseEnrollment.last_accessed_at.desc(), CourseEnrollment.enrollment_id.desc())
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        course_id: int,
        learner_id: int,
        enrollment_status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
        progress_percent: Decimal = Decimal("0.00"),
        completed_module_count: int = 0,
        total_module_count: int = 0,
        last_accessed_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> CourseEnrollment:
        """Used by enrollment services to create a learner's course enrollment record."""
        enrollment = CourseEnrollment(
            course_id=course_id,
            learner_id=learner_id,
            enrollment_status=enrollment_status,
            progress_percent=progress_percent,
            completed_module_count=completed_module_count,
            total_module_count=total_module_count,
            last_accessed_at=last_accessed_at,
            completed_at=completed_at,
        )
        self.session.add(enrollment)
        self.session.flush()
        return enrollment

    def update_progress(
        self,
        enrollment: CourseEnrollment,
        *,
        progress_percent: Decimal,
        completed_module_count: int,
        total_module_count: int,
        last_accessed_at: datetime | None | object = _UNSET,
        completed_at: datetime | None | object = _UNSET,
    ) -> CourseEnrollment:
        """Used by progress-sync services to update aggregate course progress fields."""
        enrollment.progress_percent = progress_percent
        enrollment.completed_module_count = completed_module_count
        enrollment.total_module_count = total_module_count
        if last_accessed_at is not _UNSET:
            enrollment.last_accessed_at = last_accessed_at
        if completed_at is not _UNSET:
            enrollment.completed_at = completed_at
        self.session.flush()
        return enrollment

    def update_status(
        self,
        enrollment: CourseEnrollment,
        *,
        enrollment_status: EnrollmentStatus,
        last_accessed_at: datetime | None | object = _UNSET,
        completed_at: datetime | None | object = _UNSET,
    ) -> CourseEnrollment:
        """Used by enrollment workflow services to change enrollment status metadata."""
        enrollment.enrollment_status = enrollment_status
        if last_accessed_at is not _UNSET:
            enrollment.last_accessed_at = last_accessed_at
        if completed_at is not _UNSET:
            enrollment.completed_at = completed_at
        self.session.flush()
        return enrollment

    def touch_last_accessed(
        self,
        enrollment: CourseEnrollment,
        accessed_at: datetime,
    ) -> CourseEnrollment:
        """Used by learner activity services to store the latest course access timestamp."""
        enrollment.last_accessed_at = accessed_at
        self.session.flush()
        return enrollment

    def aggregate_stats_by_educator(self, *, educator_id: int) -> list[dict]:
        """Used by educator analytics to get per-course enrollment stats for all courses owned by an educator."""
        stmt = (
            select(
                Course.course_id,
                Course.title,
                Course.status,
                func.count(
                    case((CourseEnrollment.enrollment_status != EnrollmentStatus.DROPPED, CourseEnrollment.enrollment_id), else_=None)
                ).label("total_enrollments"),
                func.count(
                    case((CourseEnrollment.enrollment_status == EnrollmentStatus.ACTIVE, CourseEnrollment.enrollment_id), else_=None)
                ).label("active_enrollments"),
                func.count(
                    case((CourseEnrollment.enrollment_status == EnrollmentStatus.COMPLETED, CourseEnrollment.enrollment_id), else_=None)
                ).label("completed_enrollments"),
                func.avg(
                    case((CourseEnrollment.enrollment_status != EnrollmentStatus.DROPPED, CourseEnrollment.progress_percent), else_=None)
                ).label("avg_progress_percent"),
            )
            .select_from(Course)
            .outerjoin(CourseEnrollment, CourseEnrollment.course_id == Course.course_id)
            .where(Course.educator_id == educator_id)
            .group_by(Course.course_id, Course.title, Course.status)
            .order_by(Course.course_id.desc())
        )

        rows = self.session.execute(stmt).all()
        return [
            {
                "course_id": row.course_id,
                "course_title": row.title,
                "status": row.status.value,
                "total_enrollments": row.total_enrollments or 0,
                "active_enrollments": row.active_enrollments or 0,
                "completed_enrollments": row.completed_enrollments or 0,
                "avg_progress_percent": float(row.avg_progress_percent) if row.avg_progress_percent is not None else None,
            }
            for row in rows
        ]

    def delete(self, enrollment: CourseEnrollment) -> None:
        """Used by enrollment-management services to remove an enrollment record."""
        self.session.delete(enrollment)
        self.session.flush()
