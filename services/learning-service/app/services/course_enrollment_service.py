from sqlalchemy.orm import Session

from app.core.uuid_codec import decode_course_uuid, decode_user_uuid, encode_course_uuid, encode_user_uuid
from app.models.course_enrollment_audit_logs import EnrollmentAuditActionType, EnrollmentAuditActorRole
from app.models.course_enrollments import EnrollmentStatus
from app.repositories.course_enrollment_audit_log_repository import CourseEnrollmentAuditLogRepository
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_repository import CourseRepository
from app.schemas.course import CourseEnrollmentLearnerResponse, CourseEnrollmentResponse
from app.services.course_enrollment_aggregate_service import CourseEnrollmentAggregateService
from app.services.identity_user_client import IdentityUserClient
from app.services.module_profile_trigger_service import ModuleProfileTriggerService
from platform_common.errors import AppServiceError, invalid_identity_response_error


class CourseEnrollmentServiceError(AppServiceError):
    pass


class CourseNotFoundError(CourseEnrollmentServiceError):
    def __init__(self) -> None:
        super().__init__("Course not found", 404)


class LearnerOnlyEnrollmentError(CourseEnrollmentServiceError):
    def __init__(self) -> None:
        super().__init__("Only learners can enrol in courses", 403)


class CourseAlreadyEnrolledError(CourseEnrollmentServiceError):
    def __init__(self) -> None:
        super().__init__("Learner already enrolled in this course", 409)


class EnrollmentNotFoundError(CourseEnrollmentServiceError):
    def __init__(self) -> None:
        super().__init__("Course enrollment not found", 404)


class EnrollmentManagementNotAllowedError(CourseEnrollmentServiceError):
    def __init__(self) -> None:
        super().__init__("Only admins or the course educator can manage this enrollment", 403)


class EducatorOnlyEnrollmentManagementError(CourseEnrollmentServiceError):
    def __init__(self) -> None:
        super().__init__("Only educators can use this endpoint", 403)


class InvalidEnrollmentStatusTransitionError(CourseEnrollmentServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, 409)


class UnsupportedEnrollmentStatusError(CourseEnrollmentServiceError):
    def __init__(self, detail: str = "Unsupported enrollment status for this endpoint") -> None:
        super().__init__(detail, 400)


class CourseEnrollmentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.enrollments = CourseEnrollmentRepository(session)
        self.audit_logs = CourseEnrollmentAuditLogRepository(session)
        self.identity_users = IdentityUserClient()
        self.aggregates = CourseEnrollmentAggregateService(session)
        self.profile_triggers = ModuleProfileTriggerService(session)

    def enrol_course(self, *, course_uuid: str, current_user: dict) -> CourseEnrollmentResponse:
        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise invalid_identity_response_error()

        if current_user.get("identity") != "Learner":
            raise LearnerOnlyEnrollmentError()

        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseNotFoundError()

        total_module_count, progress_percent = self.aggregates.build_initial_aggregate(course_id=course_id)
        existing_enrollment = self.enrollments.get_by_course_and_learner(course_id=course_id, learner_id=learner_id)
        if existing_enrollment is not None:
            if existing_enrollment.enrollment_status == EnrollmentStatus.DROPPED:
                enrollment = self.enrollments.update_progress(
                    existing_enrollment,
                    progress_percent=progress_percent,
                    completed_module_count=existing_enrollment.completed_module_count,
                    total_module_count=total_module_count,
                    completed_at=None,
                )
                enrollment = self.enrollments.update_status(
                    existing_enrollment,
                    enrollment_status=EnrollmentStatus.ACTIVE,
                    completed_at=None,
                )
                self._create_audit_log(
                    enrollment=enrollment,
                    action_type=EnrollmentAuditActionType.RE_ENROLLED,
                    actor_role=self._get_actor_role(current_user),
                    changed_by_user_id=learner_id,
                    old_status=EnrollmentStatus.DROPPED.value,
                    new_status=EnrollmentStatus.ACTIVE.value,
                    reason="Learner re-enrolled in the course",
                )
                self.session.commit()
                self.session.refresh(enrollment)
                self.profile_triggers.initialize_currently_unlocked_for_enrollment(
                    course_id=course_id,
                    learner_id=learner_id,
                )
                return self._to_response(enrollment)
            raise CourseAlreadyEnrolledError()

        enrollment = self.enrollments.create(
            course_id=course_id,
            learner_id=learner_id,
            progress_percent=progress_percent,
            completed_module_count=0,
            total_module_count=total_module_count,
        )
        self._create_audit_log(
            enrollment=enrollment,
            action_type=EnrollmentAuditActionType.ENROLLED,
            actor_role=self._get_actor_role(current_user),
            changed_by_user_id=learner_id,
            old_status=None,
            new_status=EnrollmentStatus.ACTIVE.value,
            reason="Learner enrolled in the course",
        )
        self.session.commit()
        self.session.refresh(enrollment)
        self.profile_triggers.initialize_currently_unlocked_for_enrollment(
            course_id=course_id,
            learner_id=learner_id,
        )
        return self._to_response(enrollment)

    def drop_own_enrollment(self, *, course_uuid: str, current_user: dict) -> CourseEnrollmentResponse:
        learner_id = current_user.get("id")
        if not isinstance(learner_id, int):
            raise invalid_identity_response_error()

        if current_user.get("identity") != "Learner":
            raise LearnerOnlyEnrollmentError()

        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseNotFoundError()

        enrollment = self.enrollments.get_by_course_and_learner(course_id=course_id, learner_id=learner_id)
        if enrollment is None:
            raise EnrollmentNotFoundError()

        return self._drop_active_enrollment(
            enrollment=enrollment,
            actor_id=learner_id,
            actor_role=EnrollmentAuditActorRole.LEARNER,
            reason="Enrollment dropped by learner",
            default_reason="Enrollment dropped by learner",
        )

    def list_course_enrollments(self, *, course_uuid: str, current_user: dict) -> list[CourseEnrollmentLearnerResponse]:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        actor_role = self._get_actor_role(current_user)
        if actor_role not in {EnrollmentAuditActorRole.EDUCATOR, EnrollmentAuditActorRole.ADMIN}:
            raise EnrollmentManagementNotAllowedError()

        course_id = decode_course_uuid(course_uuid)
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseNotFoundError()

        if actor_role == EnrollmentAuditActorRole.EDUCATOR and course.educator_id != actor_id:
            raise EnrollmentManagementNotAllowedError()

        enrollments = self.enrollments.list_current_by_course(course_id)
        learner_profiles = self.identity_users.lookup_users_by_ids(
            user_ids=[enrollment.learner_id for enrollment in enrollments]
        )
        return [
            self._to_learner_response(
                enrollment,
                learner_profiles.get(enrollment.learner_id),
            )
            for enrollment in enrollments
        ]

    def update_enrollment_status(
        self,
        *,
        course_uuid: str,
        learner_uuid: str,
        enrollment_status: str,
        current_user: dict,
        reason: str | None = None,
    ) -> CourseEnrollmentResponse:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        actor_role = self._get_actor_role(current_user)
        if actor_role != EnrollmentAuditActorRole.EDUCATOR:
            raise EducatorOnlyEnrollmentManagementError()

        normalized_status = enrollment_status.strip().lower()
        if normalized_status != EnrollmentStatus.DROPPED.value:
            raise UnsupportedEnrollmentStatusError("Educators can only change active enrollments to dropped")

        course_id = decode_course_uuid(course_uuid)
        learner_id = decode_user_uuid(learner_uuid)

        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseNotFoundError()

        if course.educator_id != actor_id:
            raise EnrollmentManagementNotAllowedError()

        enrollment = self.enrollments.get_by_course_and_learner(course_id=course_id, learner_id=learner_id)
        if enrollment is None:
            raise EnrollmentNotFoundError()

        return self._drop_active_enrollment(
            enrollment=enrollment,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            default_reason="Enrollment dropped by educator",
        )

    def admin_manage_enrollment(
        self,
        *,
        course_uuid: str,
        learner_uuid: str,
        enrollment_status: str,
        current_user: dict,
        reason: str | None = None,
    ) -> CourseEnrollmentResponse:
        actor_id = current_user.get("id")
        if not isinstance(actor_id, int):
            raise invalid_identity_response_error()

        actor_role = self._get_actor_role(current_user)
        if actor_role != EnrollmentAuditActorRole.ADMIN:
            raise EnrollmentManagementNotAllowedError()

        normalized_status = enrollment_status.strip().lower()
        if normalized_status not in {EnrollmentStatus.ACTIVE.value, EnrollmentStatus.DROPPED.value}:
            raise UnsupportedEnrollmentStatusError("Admins can only manage enrollments to active or dropped")

        course_id = decode_course_uuid(course_uuid)
        learner_id = decode_user_uuid(learner_uuid)

        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseNotFoundError()

        enrollment = self.enrollments.get_by_course_and_learner(course_id=course_id, learner_id=learner_id)

        if normalized_status == EnrollmentStatus.ACTIVE.value:
            return self._admin_activate_enrollment(
                enrollment=enrollment,
                course_id=course_id,
                learner_id=learner_id,
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
            )

        if enrollment is None:
            raise EnrollmentNotFoundError()

        return self._drop_active_enrollment(
            enrollment=enrollment,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            default_reason="Enrollment dropped by admin",
        )

    def _to_response(self, enrollment) -> CourseEnrollmentResponse:
        return CourseEnrollmentResponse(
            enrollmentId=enrollment.enrollment_id,
            courseId=enrollment.course_id,
            courseUuid=encode_course_uuid(enrollment.course_id),
            learnerId=enrollment.learner_id,
            learnerUuid=encode_user_uuid(enrollment.learner_id),
            enrollmentStatus=enrollment.enrollment_status.value,
            progressPercent=str(enrollment.progress_percent),
            completedModuleCount=enrollment.completed_module_count,
            totalModuleCount=enrollment.total_module_count,
            enrolledAt=enrollment.enrolled_at,
            lastAccessedAt=enrollment.last_accessed_at,
            completedAt=enrollment.completed_at,
        )

    def _to_learner_response(
        self,
        enrollment,
        learner_profile: dict[str, object] | None,
    ) -> CourseEnrollmentLearnerResponse:
        base_response = self._to_response(enrollment)
        return CourseEnrollmentLearnerResponse(
            **base_response.model_dump(),
            learnerName=learner_profile.get("userName") if learner_profile else None,
            learnerEmail=learner_profile.get("email") if learner_profile else None,
            learnerIdentity=learner_profile.get("identity") if learner_profile else None,
            learnerAccountStatus=learner_profile.get("accountStatus") if learner_profile else None,
            learnerEmailVerified=learner_profile.get("emailVerified") if learner_profile else None,
        )

    def _get_actor_role(self, current_user: dict) -> EnrollmentAuditActorRole:
        identity = current_user.get("identity")
        if identity == "Learner":
            return EnrollmentAuditActorRole.LEARNER
        if identity == "Educator":
            return EnrollmentAuditActorRole.EDUCATOR
        if identity == "Admin":
            return EnrollmentAuditActorRole.ADMIN
        raise invalid_identity_response_error()

    def _create_audit_log(
        self,
        *,
        enrollment,
        action_type: EnrollmentAuditActionType,
        actor_role: EnrollmentAuditActorRole,
        changed_by_user_id: int | None,
        old_status: str | None,
        new_status: str,
        reason: str | None,
    ) -> None:
        self.audit_logs.create(
            enrollment_id=enrollment.enrollment_id,
            course_id=enrollment.course_id,
            learner_id=enrollment.learner_id,
            action_type=action_type,
            changed_by_user_id=changed_by_user_id,
            changed_by_role=actor_role,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
        )

    def _admin_activate_enrollment(
        self,
        *,
        enrollment,
        course_id: int,
        learner_id: int,
        actor_id: int,
        actor_role: EnrollmentAuditActorRole,
        reason: str | None,
    ) -> CourseEnrollmentResponse:
        normalized_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None

        if enrollment is None:
            enrollment = self.enrollments.create(course_id=course_id, learner_id=learner_id)
            self._create_audit_log(
                enrollment=enrollment,
                action_type=EnrollmentAuditActionType.ENROLLED,
                actor_role=actor_role,
                changed_by_user_id=actor_id,
                old_status=None,
                new_status=EnrollmentStatus.ACTIVE.value,
                reason=normalized_reason or "Enrollment created by admin",
            )
            self.session.commit()
            self.session.refresh(enrollment)
            self.profile_triggers.initialize_currently_unlocked_for_enrollment(
                course_id=course_id,
                learner_id=learner_id,
            )
            return self._to_response(enrollment)

        if enrollment.enrollment_status == EnrollmentStatus.ACTIVE:
            raise InvalidEnrollmentStatusTransitionError("Learner enrollment is already active")
        if enrollment.enrollment_status != EnrollmentStatus.DROPPED:
            raise InvalidEnrollmentStatusTransitionError("Only dropped enrollments can be re-activated")

        updated_enrollment = self.enrollments.update_status(
            enrollment,
            enrollment_status=EnrollmentStatus.ACTIVE,
            completed_at=None,
        )
        self._create_audit_log(
            enrollment=updated_enrollment,
            action_type=EnrollmentAuditActionType.RE_ENROLLED,
            actor_role=actor_role,
            changed_by_user_id=actor_id,
            old_status=EnrollmentStatus.DROPPED.value,
            new_status=EnrollmentStatus.ACTIVE.value,
            reason=normalized_reason or "Enrollment re-activated by admin",
        )
        self.session.commit()
        self.session.refresh(updated_enrollment)
        self.profile_triggers.initialize_currently_unlocked_for_enrollment(
            course_id=course_id,
            learner_id=learner_id,
        )
        return self._to_response(updated_enrollment)

    def _drop_active_enrollment(
        self,
        *,
        enrollment,
        actor_id: int,
        actor_role: EnrollmentAuditActorRole,
        reason: str | None,
        default_reason: str,
    ) -> CourseEnrollmentResponse:
        if enrollment.enrollment_status == EnrollmentStatus.DROPPED:
            raise InvalidEnrollmentStatusTransitionError("Learner enrollment is already dropped")
        if enrollment.enrollment_status != EnrollmentStatus.ACTIVE:
            raise InvalidEnrollmentStatusTransitionError("Only active enrollments can be dropped")

        previous_status = enrollment.enrollment_status.value
        updated_enrollment = self.enrollments.update_status(
            enrollment,
            enrollment_status=EnrollmentStatus.DROPPED,
            completed_at=None,
        )
        self._create_audit_log(
            enrollment=updated_enrollment,
            action_type=EnrollmentAuditActionType.DROPPED,
            actor_role=actor_role,
            changed_by_user_id=actor_id,
            old_status=previous_status,
            new_status=EnrollmentStatus.DROPPED.value,
            reason=reason.strip() if isinstance(reason, str) and reason.strip() else default_reason,
        )
        self.session.commit()
        self.session.refresh(updated_enrollment)
        return self._to_response(updated_enrollment)
