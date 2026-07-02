import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.public_url import (
    PublicFrontendUrlNotConfiguredError,
    configured_public_frontend_base_url,
    normalize_public_frontend_base_url,
)
from app.core.uuid_codec import decode_course_uuid, encode_course_uuid
from app.models.courses import CourseStatus
from app.models.course_invite_token import CourseInviteToken
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_invite_token_repository import CourseInviteTokenRepository
from app.repositories.course_repository import CourseRepository
from app.services.course_enrollment_aggregate_service import CourseEnrollmentAggregateService
from app.models.course_enrollments import EnrollmentStatus
from app.models.course_enrollment_audit_logs import EnrollmentAuditActionType, EnrollmentAuditActorRole
from app.repositories.course_enrollment_audit_log_repository import CourseEnrollmentAuditLogRepository
from app.services.module_profile_trigger_service import ModuleProfileTriggerService
from platform_common.errors import AppServiceError, invalid_identity_response_error



def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_course_invite_url(token: str, public_frontend_base_url: str | None = None) -> str:
    if public_frontend_base_url:
        base = normalize_public_frontend_base_url(public_frontend_base_url) or public_frontend_base_url.rstrip("/")
    else:
        configured = configured_public_frontend_base_url()
        if configured:
            base = configured
        elif os.getenv("APP_ENV", "").strip().lower() == "production":
            raise PublicFrontendUrlNotConfiguredError("Public frontend URL is not configured")
        else:
            base = "http://localhost:8080"
    base = normalize_public_frontend_base_url(base) or base
    qs = urlencode({"token": token})
    return f"{base}/courses/join?{qs}"


class CourseInviteServiceError(AppServiceError):
    pass


class CourseInviteService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.invite_tokens = CourseInviteTokenRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.audit_logs = CourseEnrollmentAuditLogRepository(session)
        self.aggregates = CourseEnrollmentAggregateService(session)
        self.profile_triggers = ModuleProfileTriggerService(session)

    def generate_invite_link(
        self,
        *,
        course_uuid: str,
        current_user: dict,
        public_frontend_base_url: str | None = None,
    ) -> dict:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        identity = current_user.get("identity")
        if identity not in ("Educator", "Admin"):
            raise CourseInviteServiceError("Only educators or admins can generate invite links", 403)

        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseInviteServiceError("Course not found", 404)

        if identity == "Educator" and course.educator_id != actor_id:
            raise CourseInviteServiceError("Only the course educator can generate invite links for this course", 403)

        invite_token = self.invite_tokens.create(
            course_id=course_id,
            created_by=actor_id,
        )
        self.session.commit()
        self.session.refresh(invite_token)

        invite_url = _build_course_invite_url(
            invite_token.invite_uuid,
            public_frontend_base_url=public_frontend_base_url,
        )
        return {
            "inviteUuid": invite_token.invite_uuid,
            "courseUuid": course_uuid,
            "inviteUrl": invite_url,
            "isActive": True,
            "createdAt": invite_token.created_at.isoformat(),
        }

    def list_invite_links(
        self,
        *,
        course_uuid: str,
        current_user: dict,
        public_frontend_base_url: str | None = None,
    ) -> list[dict]:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        identity = current_user.get("identity")
        if identity not in ("Educator", "Admin"):
            raise CourseInviteServiceError("Only educators or admins can view invite links", 403)

        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseInviteServiceError("Course not found", 404)

        if identity == "Educator" and course.educator_id != actor_id:
            raise CourseInviteServiceError("Only the course educator can view invite links for this course", 403)

        tokens = self.invite_tokens.list_by_course(course_id)
        now = _now_utc()
        return [
            {
                "inviteUuid": t.invite_uuid,
                "courseUuid": course_uuid,
                "inviteUrl": _build_course_invite_url(
                    t.invite_uuid,
                    public_frontend_base_url=public_frontend_base_url,
                ),
                "isActive": t.is_active and (t.expires_at is None or t.expires_at >= now),
                "createdAt": t.created_at.isoformat(),
                "expiresAt": t.expires_at.isoformat() if t.expires_at else None,
            }
            for t in tokens
        ]

    def deactivate_invite_link(self, *, invite_uuid: str, current_user: dict) -> dict:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        identity = current_user.get("identity")
        if identity not in ("Educator", "Admin"):
            raise CourseInviteServiceError("Only educators or admins can deactivate invite links", 403)

        token = self.invite_tokens.get_by_uuid(invite_uuid)
        if token is None:
            raise CourseInviteServiceError("Invite link not found", 404)

        course = self.courses.get_by_id(token.course_id)
        if course is None:
            raise CourseInviteServiceError("Course not found", 404)

        if identity == "Educator" and course.educator_id != actor_id:
            raise CourseInviteServiceError("Only the course educator can deactivate invite links for this course", 403)

        self.invite_tokens.deactivate(token)
        self.session.commit()
        return {"detail": "Invite link deactivated"}

    def validate_invite_token(self, *, token: str) -> dict:
        if not token:
            raise HTTPException(status_code=400, detail="Missing token")
        invite = self.invite_tokens.get_valid_by_uuid(token)
        if invite is None:
            raise HTTPException(status_code=400, detail="Invalid or expired invite link")

        course = self.courses.get_by_id(invite.course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.status != CourseStatus.PUBLISHED:
            raise HTTPException(status_code=404, detail="Course is not available")

        return {
            "valid": True,
            "courseUuid": encode_course_uuid(course.course_id),
            "courseTitle": course.title,
            "inviteUuid": invite.invite_uuid,
        }

    def enrol_via_invite(self, *, token: str, current_user: dict) -> dict:
        if not token:
            raise HTTPException(status_code=400, detail="Missing token")

        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise invalid_identity_response_error()

        identity = current_user.get("identity")
        if identity != "Learner":
            raise HTTPException(status_code=403, detail="Only learners can enrol via invite links")

        invite = self.invite_tokens.get_valid_by_uuid(token)
        if invite is None:
            raise HTTPException(status_code=400, detail="Invalid or expired invite link")

        course = self.courses.get_by_id(invite.course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.status != CourseStatus.PUBLISHED:
            raise HTTPException(status_code=404, detail="Course is not available")

        course_id = invite.course_id
        total_module_count, progress_percent = self.aggregates.build_initial_aggregate(course_id=course_id)
        existing = self.enrollments.get_by_course_and_learner(course_id=course_id, learner_id=learner_id)

        if existing is not None:
            if existing.enrollment_status == EnrollmentStatus.DROPPED:
                self.enrollments.update_progress(
                    existing,
                    progress_percent=progress_percent,
                    completed_module_count=existing.completed_module_count,
                    total_module_count=total_module_count,
                    completed_at=None,
                )
                self.enrollments.update_status(existing, enrollment_status=EnrollmentStatus.ACTIVE, completed_at=None)
                self.audit_logs.create(
                    enrollment_id=existing.enrollment_id,
                    course_id=course_id,
                    learner_id=learner_id,
                    action_type=EnrollmentAuditActionType.RE_ENROLLED,
                    changed_by_user_id=learner_id,
                    changed_by_role=EnrollmentAuditActorRole.LEARNER,
                    old_status=EnrollmentStatus.DROPPED.value,
                    new_status=EnrollmentStatus.ACTIVE.value,
                    reason="Learner re-enrolled via invite link",
                )
                self.session.commit()
                self.profile_triggers.initialize_currently_unlocked_for_enrollment(
                    course_id=course_id,
                    learner_id=learner_id,
                )
                return {
                    "detail": "Enrolled successfully",
                    "courseUuid": encode_course_uuid(course_id),
                    "courseTitle": course.title,
                }
            # Already active
            return {
                "detail": "Already enrolled",
                "courseUuid": encode_course_uuid(course_id),
                "courseTitle": course.title,
            }

        enrollment = self.enrollments.create(
            course_id=course_id,
            learner_id=learner_id,
            progress_percent=progress_percent,
            completed_module_count=0,
            total_module_count=total_module_count,
        )
        self.audit_logs.create(
            enrollment_id=enrollment.enrollment_id,
            course_id=course_id,
            learner_id=learner_id,
            action_type=EnrollmentAuditActionType.ENROLLED,
            changed_by_user_id=learner_id,
            changed_by_role=EnrollmentAuditActorRole.LEARNER,
            old_status=None,
            new_status=EnrollmentStatus.ACTIVE.value,
            reason="Learner enrolled via invite link",
        )
        self.session.commit()
        self.profile_triggers.initialize_currently_unlocked_for_enrollment(
            course_id=course_id,
            learner_id=learner_id,
        )
        return {
            "detail": "Enrolled successfully",
            "courseUuid": encode_course_uuid(course_id),
            "courseTitle": course.title,
        }
