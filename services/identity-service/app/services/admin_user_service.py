from sqlalchemy.orm import Session

from app.core.uuid_codec import encode_user_uuid
from app.core.uuid_codec import decode_user_uuid
from app.models.audit import ChangeType
from app.models.audit import AuditAccountStatus
from app.models.user import AccountStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import AdminUserListResponse, AdminUserRead
from app.services.auth_service import role_code_to_identity
from platform_common.errors import AppServiceError


class AdminUserServiceError(AppServiceError):
    pass


class AdminUserNotFoundError(AdminUserServiceError):
    def __init__(self) -> None:
        super().__init__("User not found", 404)


class InvalidUserIdentityError(AdminUserServiceError):
    def __init__(self) -> None:
        super().__init__("Identity must be Learner or Educator", 400)


class InvalidAccountStatusError(AdminUserServiceError):
    def __init__(self) -> None:
        super().__init__("Invalid account status", 400)


class ProtectedUserUpdateError(AdminUserServiceError):
    def __init__(self) -> None:
        super().__init__("Admin users cannot be updated by this endpoint", 403)


class RoleConfigurationError(AdminUserServiceError):
    def __init__(self) -> None:
        super().__init__("Target role is not configured", 500)


class NoUserChangeRequiredError(AdminUserServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, 409)


class AdminUserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.audit_logs = AuditLogRepository(session)

    def list_users(self) -> AdminUserListResponse:
        user_rows = self.users.list_all()
        response_items: list[AdminUserRead] = []

        for user in user_rows:
            serialized_user = self._serialize_user(user)
            if "admin" in serialized_user.roleCodes:
                continue
            response_items.append(serialized_user)

        return AdminUserListResponse(users=response_items)

    def update_user_identity(
        self,
        *,
        user_uuid: str,
        identity: str,
        changed_by_user_id: int,
    ) -> AdminUserRead:
        normalized_identity = identity.strip().title()
        if normalized_identity not in {"Learner", "Educator"}:
            raise InvalidUserIdentityError()

        target_user_id = decode_user_uuid(user_uuid)
        user = self.users.get_by_id(target_user_id)
        if user is None:
            raise AdminUserNotFoundError()

        current_roles = self.roles.list_user_roles(user.user_id)
        current_role_codes = {role.role_code for role in current_roles}
        if "admin" in current_role_codes:
            raise ProtectedUserUpdateError()

        target_role_code = normalized_identity.lower()
        target_role = self.roles.get_by_code(target_role_code)
        if target_role is None:
            raise RoleConfigurationError()

        current_primary_role = current_roles[0] if current_roles else None
        if current_primary_role and current_primary_role.role_code == target_role_code:
            raise NoUserChangeRequiredError("User already has the requested identity")

        self.roles.clear_user_roles(user.user_id)
        self.roles.assign_role(user.user_id, target_role.role_id)
        self.audit_logs.create_user_role_audit_log(
            target_user_id=user.user_id,
            changed_by=changed_by_user_id,
            change_type=ChangeType.ROLE_CHANGE,
            old_role_id=current_primary_role.role_id if current_primary_role else None,
            new_role_id=target_role.role_id,
            change_reason=f"Identity updated to {normalized_identity}",
        )
        self.session.commit()
        self.session.refresh(user)
        return self._serialize_user(user)

    def update_user_status(
        self,
        *,
        user_uuid: str,
        account_status: str,
        changed_by_user_id: int,
    ) -> AdminUserRead:
        normalized_status = account_status.strip().lower()
        try:
            target_status = AccountStatus(normalized_status)
        except ValueError as exc:
            raise InvalidAccountStatusError() from exc

        target_user_id = decode_user_uuid(user_uuid)
        user = self.users.get_by_id(target_user_id)
        if user is None:
            raise AdminUserNotFoundError()

        current_roles = self.roles.list_user_roles(user.user_id)
        current_role_codes = {role.role_code for role in current_roles}
        if "admin" in current_role_codes:
            raise ProtectedUserUpdateError()

        if user.account_status == target_status:
            raise NoUserChangeRequiredError("User already has the requested account status")

        previous_status = user.account_status
        self.users.update_account_status(user, target_status)
        self.audit_logs.create_user_role_audit_log(
            target_user_id=user.user_id,
            changed_by=changed_by_user_id,
            change_type=ChangeType.STATUS_CHANGE,
            old_status=AuditAccountStatus(previous_status.value),
            new_status=AuditAccountStatus(target_status.value),
            change_reason=f"Account status updated to {target_status.value}",
        )
        self.session.commit()
        self.session.refresh(user)
        return self._serialize_user(user)

    def _serialize_user(self, user) -> AdminUserRead:
        roles = self.roles.list_user_roles(user.user_id)
        role_codes = [role.role_code for role in roles]
        primary_role_code = role_codes[0] if role_codes else None
        return AdminUserRead(
            id=user.user_id,
            userUuid=encode_user_uuid(user.user_id),
            email=user.email,
            userName=user.full_name,
            identity=role_code_to_identity(primary_role_code),
            roleCodes=role_codes,
            emailVerified=bool(user.email_verified),
            accountStatus=user.account_status.value
            if hasattr(user.account_status, "value")
            else str(user.account_status),
            createdAt=user.created_at.isoformat(),
            updatedAt=user.updated_at.isoformat(),
            lastLoginAt=user.last_login_at.isoformat() if user.last_login_at else None,
        )
