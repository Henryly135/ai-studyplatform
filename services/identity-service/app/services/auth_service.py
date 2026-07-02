import logging
import time
from datetime import timedelta

import jwt
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.email import send_password_reset_link, send_verification_link
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_token,
    hash_password,
    hash_token,
    password_hash_needs_upgrade,
    verify_password,
)
from app.core.time import now_local
from app.core.uuid_codec import encode_request_uuid, encode_user_uuid
from app.models.audit import LoginResult
from app.models.user import AccountStatus
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.educator_invite_token_repository import EducatorInviteTokenRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from platform_common.errors import AppServiceError
from platform_common.http.json_client import get_json
from platform_common.permissions.codes import (
    COURSE_CREATE,
    COURSE_ENROLLMENT_MANAGE,
    COURSE_PUBLISH,
    COURSE_UPDATE,
    LEARNING_PATH_CREATE,
    LEARNING_PATH_DELETE,
    LEARNING_PATH_MANAGE,
    LEARNING_PATH_UPDATE,
    MODULE_CREATE,
    MODULE_DELETE,
    MODULE_PUBLISH,
    MODULE_UPDATE,
    RESOURCE_MANAGE,
    RESOURCE_UPLOAD,
)

# Permissions restricted to ACTIVE educators only (PENDING educators cannot use these)
_EDUCATOR_ACTIVE_ONLY_PERMISSIONS = frozenset({
    COURSE_CREATE,
    COURSE_UPDATE,
    COURSE_PUBLISH,
    COURSE_ENROLLMENT_MANAGE,
    RESOURCE_UPLOAD,
    RESOURCE_MANAGE,
    LEARNING_PATH_CREATE,
    LEARNING_PATH_UPDATE,
    LEARNING_PATH_DELETE,
    LEARNING_PATH_MANAGE,
    MODULE_CREATE,
    MODULE_UPDATE,
    MODULE_DELETE,
    MODULE_PUBLISH,
})

logger = logging.getLogger(__name__)


def role_code_to_identity(role_code: str | None) -> str:
    if not role_code:
        return "Learner"
    rc = role_code.lower()
    if rc == "learner":
        return "Learner"
    if rc == "educator":
        return "Educator"
    if rc == "admin":
        return "Admin"
    return "Learner"


class AuthServiceError(AppServiceError):
    pass


class AuthInvalidCredentialsError(AuthServiceError):
    def __init__(self, detail: str = "Invalid credentials") -> None:
        super().__init__(detail, 401)


class AuthPendingApprovalError(AuthServiceError):
    def __init__(self) -> None:
        super().__init__("Account pending approval", 409)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = TokenRepository(session)
        self.roles = RoleRepository(session)
        self.permissions = PermissionRepository(session)
        self.approvals = ApprovalRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.educator_invite_tokens = EducatorInviteTokenRepository(session)

    def register(
        self,
        *,
        usr_name: str,
        email: str,
        password: str,
        identity: str,
        public_frontend_base_url: str | None = None,
    ) -> dict:
        if identity not in ("Learner", "Educator"):
            raise HTTPException(status_code=400, detail="Invalid request")

        existing = self.users.get_by_email(email)
        if existing:
            existing_role_codes = {role.role_code for role in self.roles.list_user_roles(existing.user_id)}
            if (
                identity == "Educator"
                and existing.account_status == AccountStatus.PENDING
                and "educator" in existing_role_codes
            ):
                pending_request = self.approvals.get_pending_request_by_user_id(existing.user_id)
                if pending_request is None:
                    pending_request = self.approvals.create_request(user_id=existing.user_id)
                    self.session.commit()
                    self._dispatch_educator_approval_notification(
                        user=existing,
                        request_id=pending_request.request_id,
                    )
                raise AuthPendingApprovalError()
            if bool(existing.email_verified):
                raise HTTPException(status_code=409, detail="Email already registered")
            # Unverified account: update credentials and resend verification
            self.users.update_password(existing, hash_password(password))
            existing.full_name = usr_name
            self.tokens.invalidate_user_tokens(existing.user_id)
            raw_token = generate_token(32)
            self.tokens.create_email_verification_token(
                user_id=existing.user_id,
                token_hash=hash_token(raw_token),
                expires_at=now_local() + timedelta(hours=settings.email_verification_token_expire_hours),
            )
            self.session.commit()
            send_verification_link(email, raw_token, frontend_base_url=public_frontend_base_url)
            return {
                "detail": "User registered. Verification email sent.",
                "user": {
                    "id": existing.user_id,
                    "userUuid": encode_user_uuid(existing.user_id),
                    "email": existing.email,
                    "userName": existing.full_name,
                    "identity": identity,
                    "emailVerified": False,
                },
            }

        #3.11
        # Educator accounts start as PENDING and should be moved to ACTIVE by an
        # admin/approval workflow later (identity/user status management).
        account_status = AccountStatus.ACTIVE if identity == "Learner" else AccountStatus.PENDING

        user = self.users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=usr_name,
            account_status=account_status,
            email_verified=False,
        )

        role_code = "learner" if identity == "Learner" else "educator"
        role = self.roles.get_by_code(role_code)
        if role:
            self.roles.assign_role(user.user_id, role.role_id)

        if identity == "Educator":
            approval_request = self.approvals.create_request(user_id=user.user_id)
        else:
            approval_request = None

        raw_token = generate_token(32)
        self.tokens.create_email_verification_token(
            user_id=user.user_id,
            token_hash=hash_token(raw_token),
            expires_at=now_local() + timedelta(hours=settings.email_verification_token_expire_hours),
        )

        self.session.commit()

        if approval_request is not None:
            self._dispatch_educator_approval_notification(user=user, request_id=approval_request.request_id)

        send_verification_link(email, raw_token, frontend_base_url=public_frontend_base_url)

        return {
            "detail": "User registered. Verification email sent.",
            "user": {
                "id": user.user_id,
                "userUuid": encode_user_uuid(user.user_id),
                "email": user.email,
                "userName": user.full_name,
                "identity": identity,
                "emailVerified": bool(user.email_verified),
            },
        }

    def _dispatch_educator_approval_notification(self, *, user, request_id: int) -> None:
        admin_user_ids = self.roles.list_user_ids_by_role_code("admin")
        if not admin_user_ids:
            return

        admin_users = [
            admin_user
            for admin_user in self.users.list_by_ids(admin_user_ids)
            if admin_user.account_status == AccountStatus.ACTIVE
        ]
        if not admin_users:
            return

        request_uuid = encode_request_uuid(request_id)
        payload = {
            "actorUserId": user.user_id,
            "actorEmail": user.email,
            "actorName": user.full_name,
            "requestUuid": request_uuid,
            "title": "New educator approval request",
            "body": f"{user.full_name} submitted an educator registration request.",
            "metadataJson": {
                "requestUuid": request_uuid,
                "educatorUserUuid": encode_user_uuid(user.user_id),
                "educatorEmail": user.email,
                "educatorName": user.full_name,
            },
            "recipients": [
                {
                    "recipient_user_id": admin_user.user_id,
                    "recipient_email": admin_user.email,
                    "recipient_name": admin_user.full_name,
                }
                for admin_user in admin_users
            ],
        }

        for attempt in range(1, 4):
            try:
                celery_app.send_task(
                    "app.tasks.notifications.dispatch_educator_approval_request_created_task",
                    args=[payload],
                    queue=settings.educator_approval_notification_queue,
                )
                return
            except Exception:
                logger.exception(
                    "Failed to enqueue educator approval notification task for request_id=%s attempt=%s",
                    request_id,
                    attempt,
                )
                if attempt < 3:
                    time.sleep(attempt)

    def verify_email(self, *, token: str | None) -> dict:
        if not token:
            raise HTTPException(status_code=400, detail="Missing token")

        token_row = self.tokens.get_valid_email_verification_token(hash_token(token))
        if not token_row:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")

        user = self.users.get_by_id(token_row.user_id)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")

        self.users.mark_email_verified(user)
        self.tokens.invalidate_token(email_verification_token=token_row)
        self.session.commit()

        return {"detail": "Email verified successfully"}

    def resend_verification(self, *, email: str | None, public_frontend_base_url: str | None = None) -> dict:
        if not email:
            return {"detail": "If the account exists, a verification email has been sent"}

        user = self.users.get_by_email(email)
        if not user or bool(user.email_verified):
            return {"detail": "If the account exists, a verification email has been sent"}

        self.tokens.invalidate_user_tokens(user.user_id)

        raw_token = generate_token(32)
        self.tokens.create_email_verification_token(
            user_id=user.user_id,
            token_hash=hash_token(raw_token),
            expires_at=now_local() + timedelta(hours=settings.email_verification_token_expire_hours),
        )
        self.session.commit()

        send_verification_link(email, raw_token, frontend_base_url=public_frontend_base_url)
        return {"detail": "If the account exists, a verification email has been sent"}

    def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        user = self.users.get_by_email(email)
        if not user:
            self._record_login_attempt(
                email=email,
                result=LoginResult.FAILED,
                failure_reason="invalid_email_or_password",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthInvalidCredentialsError()

        if not bool(user.email_verified):
            self._record_login_attempt(
                email=email,
                user_id=user.user_id,
                result=LoginResult.FAILED,
                failure_reason="email_not_verified",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthInvalidCredentialsError("Email not verified")

        if not verify_password(password, user.password_hash):
            self._record_login_attempt(
                email=email,
                user_id=user.user_id,
                result=LoginResult.FAILED,
                failure_reason="invalid_email_or_password",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthInvalidCredentialsError()

        if password_hash_needs_upgrade(user.password_hash):
            self.users.update_password(user, hash_password(password))

        # DEACTIVATED and REJECTED accounts cannot log in.
        # PENDING educators CAN log in after email verification but will have restricted permissions.
        if user.account_status in (AccountStatus.DEACTIVATED, AccountStatus.REJECTED):
            self._record_login_attempt(
                email=email,
                user_id=user.user_id,
                result=LoginResult.FAILED,
                failure_reason=self._account_status_failure_reason(user.account_status),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthInvalidCredentialsError(self._account_status_error_detail(user.account_status))

        self.users.update_last_login(user)
        self.audit_logs.create_login_audit_log(
            user_id=user.user_id,
            email_attempted=email,
            login_result=LoginResult.SUCCESS,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.commit()

        roles = self.roles.list_user_roles(user.user_id)
        role_code = roles[0].role_code if roles else None
        identity = role_code_to_identity(role_code)
        should_show_global_profile_init_prompt = self._should_show_global_profile_init_prompt(
            user_id=user.user_id,
            identity=identity,
        )

        access_token = create_access_token(user.user_id, identity)
        return {
            "accessToken": access_token,
            "tokenType": "bearer",
            "expiresIn": settings.jwt_expire_seconds,
            "shouldShowGlobalProfileInitPrompt": should_show_global_profile_init_prompt,
            "user": {
                "id": user.user_id,
                "userUuid": encode_user_uuid(user.user_id),
                "email": user.email,
                "userName": user.full_name,
                "identity": identity,
                "emailVerified": bool(user.email_verified),
                "accountStatus": user.account_status.value,
            },
        }

    def _should_show_global_profile_init_prompt(self, *, user_id: int, identity: str) -> bool:
        if identity != "Learner":
            return False

        login_count = self.audit_logs.count_successful_login_audit_logs(user_id)
        if login_count > 1:
            return False

        try:
            return not self._fetch_global_profile_exists(user_id=user_id)
        except Exception:
            logger.exception(
                "Failed to determine learner global profile existence during login",
                extra={"userId": user_id},
            )
            return False

    def _fetch_global_profile_exists(self, *, user_id: int) -> bool:
        payload = get_json(
            url=f"{settings.ai_service_url}/internal/profiles/global-exists/{user_id}",
            headers={"X-Internal-Token": settings.internal_api_token},
            timeout=5,
        )
        exists = payload.get("exists")
        return exists is True

    def change_password(self, *, user_id: int, current_password: str, new_password: str) -> dict:
        user = self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        self.users.update_password(user, hash_password(new_password))
        self.session.commit()

        return {"detail": "Password changed successfully"}

    def forgot_password(self, *, email: str | None, public_frontend_base_url: str | None = None) -> dict:
        if not email:
            return {"detail": "If the account exists, a password reset email has been sent"}

        user = self.users.get_by_email(email)
        if not user or not bool(user.email_verified):
            return {"detail": "If the account exists, a password reset email has been sent"}

        self.tokens.invalidate_user_tokens(user.user_id)

        raw_token = generate_token(32)
        self.tokens.create_password_reset_token(
            user_id=user.user_id,
            token_hash=hash_token(raw_token),
            expires_at=now_local() + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )
        self.session.commit()

        send_password_reset_link(email, raw_token, frontend_base_url=public_frontend_base_url)
        return {"detail": "If the account exists, a password reset email has been sent"}

    def reset_password(self, *, token: str | None, new_password: str) -> dict:
        if not token:
            raise HTTPException(status_code=400, detail="Missing token")

        token_row = self.tokens.get_valid_password_reset_token(hash_token(token))
        if not token_row:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        user = self.users.get_by_id(token_row.user_id)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        self.users.update_password(user, hash_password(new_password))
        self.tokens.invalidate_token(password_reset_token=token_row)
        self.session.commit()

        return {"detail": "Password reset successfully"}

    def get_current_user(self, token: str) -> dict:
        user, identity, _ = self._resolve_current_user(token)

        return {
            "id": user.user_id,
            "userUuid": encode_user_uuid(user.user_id),
            "email": user.email,
            "userName": user.full_name,
            "identity": identity,
            "emailVerified": bool(user.email_verified),
            "accountStatus": user.account_status.value,
        }

    def get_current_user_permissions(self, token: str) -> dict:
        user, _, roles = self._resolve_current_user(token)

        role_id = roles[0].role_id if roles else None
        role_code = roles[0].role_code if roles else None
        permissions = self.permissions.list_by_role(role_id) if role_id else []

        # PENDING educators have restricted permissions: filter out modification permissions
        is_pending_educator = (
            role_code == "educator" and user.account_status == AccountStatus.PENDING
        )
        if is_pending_educator:
            permissions = [
                p for p in permissions
                if p.permission_code not in _EDUCATOR_ACTIVE_ONLY_PERMISSIONS
            ]

        return {
            "permissions": [
                {
                    "permissionId": permission.permission_id,
                    "permissionCode": permission.permission_code,
                    "permissionName": permission.permission_name,
                    "description": permission.description,
                }
                for permission in permissions
            ]
        }

    def _resolve_current_user(self, token: str):
        try:
            payload = decode_access_token(token)
            uid = int(payload["sub"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
            raise AuthInvalidCredentialsError()

        user = self.users.get_by_id(uid)
        if not user:
            raise AuthInvalidCredentialsError()
        # DEACTIVATED and REJECTED accounts cannot use any authenticated endpoints
        if user.account_status in (AccountStatus.DEACTIVATED, AccountStatus.REJECTED):
            raise AuthInvalidCredentialsError()

        roles = self.roles.list_user_roles(user.user_id)
        role_code = roles[0].role_code if roles else None
        identity = role_code_to_identity(role_code)

        return user, identity, roles

    def _record_login_attempt(
        self,
        *,
        email: str,
        result: LoginResult,
        user_id: int | None = None,
        failure_reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.audit_logs.create_login_audit_log(
            user_id=user_id,
            email_attempted=email,
            login_result=result,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.commit()

    def _account_status_failure_reason(self, account_status: AccountStatus) -> str:
        if account_status == AccountStatus.REJECTED:
            return "account_rejected"
        if account_status == AccountStatus.DEACTIVATED:
            return "account_deactivated"
        return "invalid_account_status"

    def _account_status_error_detail(self, account_status: AccountStatus) -> str:
        if account_status == AccountStatus.REJECTED:
            return "Account rejected"
        if account_status == AccountStatus.DEACTIVATED:
            return "Account deactivated"
        return "Account not active"

    def generate_educator_invite_token(self, *, created_by_user_id: int) -> dict:
        """Admin generates a one-time educator invite token. Returns the raw token and invite URL."""
        raw_token = generate_token(32)
        token_hash = hash_token(raw_token)
        invite_token = self.educator_invite_tokens.create(
            created_by_user_id=created_by_user_id,
            token_hash=token_hash,
            expires_at=now_local() + timedelta(days=7),
        )
        self.session.commit()
        self.session.refresh(invite_token)
        return {
            "inviteUuid": invite_token.invite_uuid,
            "rawToken": raw_token,
            "expiresAt": invite_token.expires_at.isoformat(),
        }

    def validate_educator_invite_token(self, *, token: str) -> dict:
        """Public endpoint to validate an educator invite token before registration."""
        if not token:
            raise HTTPException(status_code=400, detail="Missing token")
        token_row = self.educator_invite_tokens.get_valid_by_token_hash(hash_token(token))
        if not token_row:
            raise HTTPException(status_code=400, detail="Invalid or expired invite token")
        return {
            "valid": True,
            "expiresAt": token_row.expires_at.isoformat(),
        }

    def register_via_educator_invite(
        self,
        *,
        usr_name: str,
        email: str,
        password: str,
        invite_token: str,
        public_frontend_base_url: str | None = None,
    ) -> dict:
        """Register an educator via a one-time invite link. Sets account_status=ACTIVE immediately."""
        if not invite_token:
            raise HTTPException(status_code=400, detail="Missing invite token")

        token_row = self.educator_invite_tokens.get_valid_by_token_hash(hash_token(invite_token))
        if not token_row:
            raise HTTPException(status_code=400, detail="Invalid or expired invite token")

        existing = self.users.get_by_email(email)
        if existing and bool(existing.email_verified):
            raise HTTPException(status_code=409, detail="Email already registered")

        if existing:
            # Unverified existing account: update and reuse
            self.users.update_password(existing, hash_password(password))
            existing.full_name = usr_name
            existing.account_status = AccountStatus.ACTIVE
            self.tokens.invalidate_user_tokens(existing.user_id)
            raw_verification_token = generate_token(32)
            self.tokens.create_email_verification_token(
                user_id=existing.user_id,
                token_hash=hash_token(raw_verification_token),
                expires_at=now_local() + timedelta(hours=settings.email_verification_token_expire_hours),
            )
            self.educator_invite_tokens.mark_used(token_row, existing.user_id)
            self.session.commit()
            send_verification_link(email, raw_verification_token, frontend_base_url=public_frontend_base_url)
            return {
                "detail": "User registered via invite. Verification email sent.",
                "user": {
                    "id": existing.user_id,
                    "userUuid": encode_user_uuid(existing.user_id),
                    "email": existing.email,
                    "userName": existing.full_name,
                    "identity": "Educator",
                    "emailVerified": False,
                },
            }

        user = self.users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=usr_name,
            account_status=AccountStatus.ACTIVE,  # Invite-registered educators are immediately active
            email_verified=False,
        )

        role = self.roles.get_by_code("educator")
        if role:
            self.roles.assign_role(user.user_id, role.role_id)

        raw_verification_token = generate_token(32)
        self.tokens.create_email_verification_token(
            user_id=user.user_id,
            token_hash=hash_token(raw_verification_token),
            expires_at=now_local() + timedelta(hours=settings.email_verification_token_expire_hours),
        )
        self.educator_invite_tokens.mark_used(token_row, user.user_id)
        self.session.commit()

        send_verification_link(email, raw_verification_token, frontend_base_url=public_frontend_base_url)

        return {
            "detail": "User registered via invite. Verification email sent.",
            "user": {
                "id": user.user_id,
                "userUuid": encode_user_uuid(user.user_id),
                "email": user.email,
                "userName": user.full_name,
                "identity": "Educator",
                "emailVerified": False,
            },
        }
