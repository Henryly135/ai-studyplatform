from datetime import timedelta

from app.core.time import now_local
from app.models.audit import AuditAccountStatus, ChangeType, LoginResult
from app.models.educator_approval_request import RequestStatus
from app.models.educator_invite_token import EducatorInviteToken
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import AccountStatus
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.educator_invite_token_repository import EducatorInviteTokenRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository


def test_user_repository_creates_lists_and_updates_user(db_session):
    # Tests user repository create, lookup, list, and mutable account fields.
    repo = UserRepository(db_session)
    user = repo.create(
        email="learner@example.com",
        password_hash="hash",
        full_name="Learner One",
        account_status=AccountStatus.PENDING,
    )

    repo.mark_email_verified(user)
    repo.update_account_status(user, AccountStatus.ACTIVE)
    repo.update_password(user, "new-hash")
    repo.update_last_login(user)

    assert repo.get_by_email("learner@example.com").user_id == user.user_id
    assert repo.list_by_ids([user.user_id])[0].password_hash == "new-hash"
    assert repo.list_all()[0].account_status == AccountStatus.ACTIVE


def test_role_and_permission_repositories_manage_assignments(db_session):
    # Tests role assignment plus role and permission lookup queries.
    user = UserRepository(db_session).create(email="u@example.com", password_hash="h", full_name="User")
    role = Role(role_code="learner", role_name="Learner", description="Learner role")
    permission = Permission(permission_code="user:read", permission_name="Read users", description=None)
    db_session.add_all([role, permission])
    db_session.flush()
    db_session.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    db_session.flush()
    roles = RoleRepository(db_session)
    permissions = PermissionRepository(db_session)

    roles.assign_role(user.user_id, role.role_id)

    assert roles.get_by_code("learner").role_id == role.role_id
    assert roles.list_user_roles(user.user_id)[0].role_code == "learner"
    assert roles.list_roles_by_user_ids([user.user_id])[user.user_id][0].role_code == "learner"
    assert roles.list_user_ids_by_role_code("learner") == [user.user_id]
    assert permissions.get_by_code("user:read").permission_id == permission.permission_id
    assert permissions.list_by_role(role.role_id)[0].permission_code == "user:read"


def test_token_repository_creates_validates_and_invalidates_tokens(db_session):
    # Tests email verification and password reset token lifecycle queries.
    user = UserRepository(db_session).create(email="u@example.com", password_hash="h", full_name="User")
    repo = TokenRepository(db_session)
    expires_at = now_local() + timedelta(hours=1)
    email_token = repo.create_email_verification_token(user_id=user.user_id, token_hash="email-hash", expires_at=expires_at)
    reset_token = repo.create_password_reset_token(user_id=user.user_id, token_hash="reset-hash", expires_at=expires_at)

    assert repo.get_valid_email_verification_token("email-hash").token_id == email_token.token_id
    assert repo.get_valid_password_reset_token("reset-hash").token_id == reset_token.token_id

    repo.invalidate_token(email_verification_token=email_token, password_reset_token=reset_token)

    assert repo.get_valid_email_verification_token("email-hash") is None
    assert repo.get_valid_password_reset_token("reset-hash") is None


def test_token_repository_invalidates_all_active_user_tokens(db_session):
    # Tests bulk invalidation marks every active token for the same user as used.
    user = UserRepository(db_session).create(email="u@example.com", password_hash="h", full_name="User")
    repo = TokenRepository(db_session)
    expires_at = now_local() + timedelta(hours=1)
    email_token = repo.create_email_verification_token(user_id=user.user_id, token_hash="email-hash", expires_at=expires_at)
    reset_token = repo.create_password_reset_token(user_id=user.user_id, token_hash="reset-hash", expires_at=expires_at)

    repo.invalidate_user_tokens(user.user_id)

    assert email_token.used_at is not None
    assert reset_token.used_at is not None


def test_approval_repository_creates_filters_and_reviews_requests(db_session):
    # Tests approval request creation, pending/reviewed filters, and review metadata updates.
    user = UserRepository(db_session).create(email="u@example.com", password_hash="h", full_name="User")
    repo = ApprovalRepository(db_session)
    request = repo.create_request(user_id=user.user_id, supporting_info="info", supporting_file_url="file")

    assert repo.get_pending_request_by_user_id(user.user_id).request_id == request.request_id
    assert repo.get_pending_requests()[0].supporting_info == "info"

    repo.update_status(request, request_status=RequestStatus.APPROVED, reviewed_by=user.user_id, review_comment="ok")

    assert repo.get_reviewed_requests(request_status=RequestStatus.APPROVED)[0].review_comment == "ok"
    assert repo.list_by_user(user.user_id)[0].request_status == RequestStatus.APPROVED


def test_invite_token_repository_creates_marks_and_lists_tokens(db_session):
    # Tests educator invite token valid lookup, used marker, and creator listing.
    user = UserRepository(db_session).create(email="admin@example.com", password_hash="h", full_name="Admin")
    repo = EducatorInviteTokenRepository(db_session)
    token = EducatorInviteToken(
        invite_id=1,
        invite_uuid="invite-uuid",
        created_by_user_id=user.user_id,
        token_hash="invite-hash",
        expires_at=now_local() + timedelta(days=1),
    )
    db_session.add(token)
    db_session.flush()

    assert repo.get_valid_by_token_hash("invite-hash").invite_uuid == token.invite_uuid
    assert repo.get_by_uuid(token.invite_uuid).token_hash == "invite-hash"

    repo.mark_used(token, used_by_user_id=user.user_id)

    assert repo.get_valid_by_token_hash("invite-hash") is None
    assert repo.list_by_creator(user.user_id)[0].used_by_user_id == user.user_id


def test_audit_log_repository_records_and_counts_audits(db_session):
    # Tests role-change audit logs, login audit logs, and successful-login counting.
    user = UserRepository(db_session).create(email="u@example.com", password_hash="h", full_name="User")
    repo = AuditLogRepository(db_session)
    role_log = repo.create_user_role_audit_log(
        target_user_id=user.user_id,
        changed_by=user.user_id,
        change_type=ChangeType.STATUS_CHANGE,
        old_status=AuditAccountStatus.PENDING,
        new_status=AuditAccountStatus.ACTIVE,
        change_reason="activate",
    )
    login_log = repo.create_login_audit_log(
        user_id=user.user_id,
        email_attempted=user.email,
        login_result=LoginResult.SUCCESS,
        ip_address="127.0.0.1",
    )

    assert repo.list_user_role_audit_logs(user.user_id)[0].audit_id == role_log.audit_id
    assert repo.list_login_audit_logs(user.user_id)[0].log_id == login_log.log_id
    assert repo.count_successful_login_audit_logs(user.user_id) == 1
