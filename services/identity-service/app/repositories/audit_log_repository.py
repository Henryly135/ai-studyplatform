from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import (
    AuditAccountStatus,
    ChangeType,
    LoginAuditLog,
    LoginResult,
    UserRoleAuditLog,
)


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_user_role_audit_log(
        self,
        *,
        target_user_id: int,
        change_type: ChangeType,
        changed_by: int | None = None,
        old_role_id: int | None = None,
        new_role_id: int | None = None,
        old_status: AuditAccountStatus | None = None,
        new_status: AuditAccountStatus | None = None,
        change_reason: str | None = None,
    ) -> UserRoleAuditLog:
        """Used by admin and approval services to record role or account-status changes."""
        audit_log = UserRoleAuditLog(
            target_user_id=target_user_id,
            change_type=change_type,
            changed_by=changed_by,
            old_role_id=old_role_id,
            new_role_id=new_role_id,
            old_status=old_status,
            new_status=new_status,
            change_reason=change_reason,
        )
        self.session.add(audit_log)
        self.session.flush()
        return audit_log

    def create_login_audit_log(
        self,
        *,
        email_attempted: str,
        login_result: LoginResult,
        user_id: int | None = None,
        failure_reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginAuditLog:
        """Used by authentication services to record login success or failure events."""
        audit_log = LoginAuditLog(
            user_id=user_id,
            email_attempted=email_attempted,
            login_result=login_result,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(audit_log)
        self.session.flush()
        return audit_log

    def list_user_role_audit_logs(self, target_user_id: int) -> list[UserRoleAuditLog]:
        """Used by admin audit services to review role and status changes for a user."""
        stmt = (
            select(UserRoleAuditLog)
            .where(UserRoleAuditLog.target_user_id == target_user_id)
            .order_by(UserRoleAuditLog.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def list_login_audit_logs(self, user_id: int) -> list[LoginAuditLog]:
        """Used by admin audit services to review login history for a user."""
        stmt = (
            select(LoginAuditLog)
            .where(LoginAuditLog.user_id == user_id)
            .order_by(LoginAuditLog.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def count_successful_login_audit_logs(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(LoginAuditLog).where(
            LoginAuditLog.user_id == user_id,
            LoginAuditLog.login_result == LoginResult.SUCCESS,
        )
        return int(self.session.scalar(stmt) or 0)
