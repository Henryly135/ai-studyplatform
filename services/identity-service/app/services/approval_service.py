import logging

from app.core.email import send_educator_approval_result_email
from sqlalchemy.orm import Session

from app.core.uuid_codec import decode_request_uuid, encode_request_uuid, encode_user_uuid
from app.models.audit import AuditAccountStatus, ChangeType
from app.models.educator_approval_request import RequestStatus
from app.models.user import AccountStatus
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import EducatorApprovalListResponse, EducatorApprovalRead
from app.services.auth_service import role_code_to_identity
from platform_common.errors import AppServiceError

logger = logging.getLogger(__name__)


class ApprovalServiceError(AppServiceError):
    pass


class EducatorApprovalNotFoundError(ApprovalServiceError):
    def __init__(self) -> None:
        super().__init__("Educator approval request not found", 404)


class InvalidApprovalActionError(ApprovalServiceError):
    def __init__(self) -> None:
        super().__init__("Approval action must be approve or reject", 400)


class ApprovalAlreadyReviewedError(ApprovalServiceError):
    def __init__(self) -> None:
        super().__init__("Educator approval request has already been reviewed", 409)


class ApprovalUserNotFoundError(ApprovalServiceError):
    def __init__(self) -> None:
        super().__init__("Approval target user not found", 404)


class ApprovalRoleConfigurationError(ApprovalServiceError):
    def __init__(self) -> None:
        super().__init__("Educator role is not configured for the approval target", 500)


class ApprovalUserStateError(ApprovalServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, 409)


class InvalidApprovalHistoryStatusError(ApprovalServiceError):
    def __init__(self) -> None:
        super().__init__("History status must be reviewed, approved, or rejected", 400)


class ApprovalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.approvals = ApprovalRepository(session)
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.audit_logs = AuditLogRepository(session)

    def list_requests(self) -> EducatorApprovalListResponse:
        requests = self.approvals.get_pending_requests()
        return EducatorApprovalListResponse(
            requests=[self._serialize_request(request) for request in requests]
        )

    def list_reviewed_requests(self, *, status: str) -> EducatorApprovalListResponse:
        normalized_status = status.strip().lower()
        request_status: RequestStatus | None
        if normalized_status == "reviewed":
            request_status = None
        elif normalized_status == "approved":
            request_status = RequestStatus.APPROVED
        elif normalized_status == "rejected":
            request_status = RequestStatus.REJECTED
        else:
            raise InvalidApprovalHistoryStatusError()

        requests = self.approvals.get_reviewed_requests(request_status=request_status)
        return EducatorApprovalListResponse(
            requests=[self._serialize_request(request) for request in requests]
        )

    def get_request(self, request_id: int) -> EducatorApprovalRead:
        request = self.approvals.get_by_id(request_id)
        if request is None:
            raise EducatorApprovalNotFoundError()
        return self._serialize_request(request)

    def get_request_by_uuid(self, request_uuid: str) -> EducatorApprovalRead:
        return self.get_request(decode_request_uuid(request_uuid))

    def review_request(
        self,
        *,
        request_id: int,
        action: str,
        review_comment: str | None,
        reviewed_by_user_id: int,
    ) -> EducatorApprovalRead:
        normalized_action = action.strip().lower()
        if normalized_action not in {"approve", "reject"}:
            raise InvalidApprovalActionError()

        request = self.approvals.get_by_id(request_id)
        if request is None:
            raise EducatorApprovalNotFoundError()
        if request.request_status != RequestStatus.PENDING:
            raise ApprovalAlreadyReviewedError()

        user = self.users.get_by_id(request.user_id)
        if user is None:
            raise ApprovalUserNotFoundError()

        educator_role = self.roles.get_by_code("educator")
        if educator_role is None:
            raise ApprovalRoleConfigurationError()

        current_roles = self.roles.list_user_roles(user.user_id)
        current_role_codes = {role.role_code for role in current_roles}
        if "educator" not in current_role_codes:
            raise ApprovalRoleConfigurationError()
        if not bool(user.email_verified):
            raise ApprovalUserStateError("Educator account must verify email before review")
        if user.account_status != AccountStatus.PENDING:
            raise ApprovalUserStateError("Only pending educator accounts can be reviewed")

        target_request_status = (
            RequestStatus.APPROVED if normalized_action == "approve" else RequestStatus.REJECTED
        )
        target_account_status = (
            AccountStatus.ACTIVE if normalized_action == "approve" else AccountStatus.REJECTED
        )

        self.approvals.update_status(
            request,
            request_status=target_request_status,
            reviewed_by=reviewed_by_user_id,
            review_comment=review_comment,
        )
        self.users.update_account_status(user, target_account_status)
        self.audit_logs.create_user_role_audit_log(
            target_user_id=user.user_id,
            changed_by=reviewed_by_user_id,
            change_type=ChangeType.APPROVAL_RESULT,
            old_role_id=educator_role.role_id,
            new_role_id=educator_role.role_id,
            old_status=AuditAccountStatus.PENDING,
            new_status=AuditAccountStatus(target_account_status.value),
            change_reason=review_comment or f"Educator approval {target_request_status.value}",
        )
        self.session.commit()
        self.session.refresh(request)
        self.session.refresh(user)
        try:
            send_educator_approval_result_email(
                user.email,
                user.full_name,
                target_request_status.value,
                review_comment,
            )
        except Exception:
            logger.exception(
                "Failed to send educator approval result email for user_id=%s",
                user.user_id,
            )
        return self._serialize_request(request)

    def review_request_by_uuid(
        self,
        *,
        request_uuid: str,
        action: str,
        review_comment: str | None,
        reviewed_by_user_id: int,
    ) -> EducatorApprovalRead:
        return self.review_request(
            request_id=decode_request_uuid(request_uuid),
            action=action,
            review_comment=review_comment,
            reviewed_by_user_id=reviewed_by_user_id,
        )

    def _serialize_request(self, request) -> EducatorApprovalRead:
        user = self.users.get_by_id(request.user_id)
        if user is None:
            raise ApprovalUserNotFoundError()

        user_roles = self.roles.list_user_roles(user.user_id)
        primary_role_code = user_roles[0].role_code if user_roles else None
        reviewer = self.users.get_by_id(request.reviewed_by) if request.reviewed_by else None

        return EducatorApprovalRead(
            requestUuid=encode_request_uuid(request.request_id),
            requestStatus=request.request_status.value
            if hasattr(request.request_status, "value")
            else str(request.request_status),
            submittedAt=request.submitted_at.isoformat(),
            updatedAt=request.updated_at.isoformat(),
            reviewedAt=request.reviewed_at.isoformat() if request.reviewed_at else None,
            reviewComment=request.review_comment,
            supportingInfo=request.supporting_info,
            supportingFileUrl=request.supporting_file_url,
            userId=user.user_id,
            userUuid=encode_user_uuid(user.user_id),
            email=user.email,
            userName=user.full_name,
            identity=role_code_to_identity(primary_role_code),
            accountStatus=user.account_status.value
            if hasattr(user.account_status, "value")
            else str(user.account_status),
            emailVerified=bool(user.email_verified),
            reviewerUserId=reviewer.user_id if reviewer else None,
            reviewerUserUuid=encode_user_uuid(reviewer.user_id) if reviewer else None,
            reviewerEmail=reviewer.email if reviewer else None,
            reviewerName=reviewer.full_name if reviewer else None,
        )
