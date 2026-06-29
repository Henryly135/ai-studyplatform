from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course_enrollment_audit_logs import (
    CourseEnrollmentAuditLog,
    EnrollmentAuditActionType,
    EnrollmentAuditActorRole,
)


class CourseEnrollmentAuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        enrollment_id: int,
        course_id: int,
        learner_id: int,
        action_type: EnrollmentAuditActionType,
        changed_by_role: EnrollmentAuditActorRole,
        new_status: str,
        changed_by_user_id: int | None = None,
        old_status: str | None = None,
        reason: str | None = None,
    ) -> CourseEnrollmentAuditLog:
        """Used by enrollment workflow services to persist each enrollment state transition."""
        audit_log = CourseEnrollmentAuditLog(
            enrollment_id=enrollment_id,
            course_id=course_id,
            learner_id=learner_id,
            action_type=action_type,
            changed_by_user_id=changed_by_user_id,
            changed_by_role=changed_by_role,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
        )
        self.session.add(audit_log)
        self.session.flush()
        return audit_log

    def list_by_enrollment(self, enrollment_id: int) -> list[CourseEnrollmentAuditLog]:
        """Used by enrollment detail services to review a single enrollment's audit history."""
        stmt = (
            select(CourseEnrollmentAuditLog)
            .where(CourseEnrollmentAuditLog.enrollment_id == enrollment_id)
            .order_by(CourseEnrollmentAuditLog.created_at.desc(), CourseEnrollmentAuditLog.audit_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_course(self, course_id: int) -> list[CourseEnrollmentAuditLog]:
        """Used by course management services to review enrollment changes within a course."""
        stmt = (
            select(CourseEnrollmentAuditLog)
            .where(CourseEnrollmentAuditLog.course_id == course_id)
            .order_by(CourseEnrollmentAuditLog.created_at.desc(), CourseEnrollmentAuditLog.audit_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_learner(self, learner_id: int) -> list[CourseEnrollmentAuditLog]:
        """Used by learner support services to review a learner's enrollment history."""
        stmt = (
            select(CourseEnrollmentAuditLog)
            .where(CourseEnrollmentAuditLog.learner_id == learner_id)
            .order_by(CourseEnrollmentAuditLog.created_at.desc(), CourseEnrollmentAuditLog.audit_id.desc())
        )
        return list(self.session.scalars(stmt))
