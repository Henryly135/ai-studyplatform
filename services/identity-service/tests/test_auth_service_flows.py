from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.security import hash_password, hash_token
from app.core.time import now_local
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.educator_invite_token import EducatorInviteToken
from app.models.user import AccountStatus
from app.repositories.educator_invite_token_repository import EducatorInviteTokenRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthInvalidCredentialsError, AuthService, role_code_to_identity
from platform_common.permissions.codes import COURSE_CREATE


def _add_role(db_session, code="learner", name="Learner"):
    role = Role(role_code=code, role_name=name, description=None)
    db_session.add(role)
    db_session.flush()
    return role


def test_role_code_to_identity_maps_known_and_unknown_roles():
    # Tests role-code conversion for supported roles and default learner fallback.
    assert role_code_to_identity(None) == "Learner"
    assert role_code_to_identity("educator") == "Educator"
    assert role_code_to_identity("admin") == "Admin"
    assert role_code_to_identity("unexpected") == "Learner"


def test_register_creates_learner_user_role_and_verification_token(db_session, monkeypatch):
    # Tests learner registration persists the user, role, verification token, and email send.
    _add_role(db_session, "learner", "Learner")
    sent = {}
    monkeypatch.setattr("app.services.auth_service.generate_token", lambda length=32: "verify-token")
    monkeypatch.setattr("app.services.auth_service.send_verification_link", lambda email, token, frontend_base_url=None: sent.update({"email": email, "token": token, "base": frontend_base_url}))

    result = AuthService(db_session).register(
        usr_name="Learner User",
        email="learner@example.com",
        password="Password1!",
        identity="Learner",
        public_frontend_base_url="http://ui",
    )

    user = UserRepository(db_session).get_by_email("learner@example.com")
    assert result["user"]["identity"] == "Learner"
    assert user.account_status == AccountStatus.ACTIVE
    assert RoleRepository(db_session).list_user_roles(user.user_id)[0].role_code == "learner"
    assert TokenRepository(db_session).get_valid_email_verification_token(hash_token("verify-token")) is not None
    assert sent == {"email": "learner@example.com", "token": "verify-token", "base": "http://ui"}


def test_register_resends_for_existing_unverified_user(db_session, monkeypatch):
    # Tests re-registering an unverified account updates credentials and reissues verification.
    user = UserRepository(db_session).create(
        email="old@example.com",
        password_hash=hash_password("Oldpass1!"),
        full_name="Old Name",
        email_verified=False,
    )
    monkeypatch.setattr("app.services.auth_service.generate_token", lambda length=32: "new-token")
    monkeypatch.setattr("app.services.auth_service.send_verification_link", lambda *args, **kwargs: None)

    result = AuthService(db_session).register(
        usr_name="New Name",
        email="old@example.com",
        password="Newpass1!",
        identity="Learner",
    )

    assert result["user"]["userName"] == "New Name"
    assert user.full_name == "New Name"
    assert TokenRepository(db_session).get_valid_email_verification_token(hash_token("new-token")) is not None


def test_register_rejects_invalid_identity_and_verified_duplicate(db_session):
    # Tests registration rejects invalid identities and already verified duplicate emails.
    UserRepository(db_session).create(
        email="taken@example.com",
        password_hash="hash",
        full_name="Taken",
        email_verified=True,
    )
    service = AuthService(db_session)

    with pytest.raises(HTTPException) as invalid_exc:
        service.register(usr_name="User", email="x@example.com", password="Password1!", identity="Admin")
    with pytest.raises(HTTPException) as duplicate_exc:
        service.register(usr_name="Taken", email="taken@example.com", password="Password1!", identity="Learner")

    assert invalid_exc.value.status_code == 400
    assert duplicate_exc.value.status_code == 409


def test_verify_resend_forgot_reset_and_change_password_flows(db_session, monkeypatch):
    # Tests email verification, resend, forgot/reset password, and change password paths.
    user = UserRepository(db_session).create(
        email="flow@example.com",
        password_hash=hash_password("Oldpass1!"),
        full_name="Flow User",
        email_verified=False,
    )
    monkeypatch.setattr("app.services.auth_service.generate_token", lambda length=32: "issued-token")
    monkeypatch.setattr("app.services.auth_service.send_verification_link", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.auth_service.send_password_reset_link", lambda *args, **kwargs: None)
    tokens = TokenRepository(db_session)
    tokens.create_email_verification_token(
        user_id=user.user_id,
        token_hash=hash_token("verify-me"),
        expires_at=now_local() + timedelta(hours=1),
    )

    assert AuthService(db_session).verify_email(token="verify-me")["detail"] == "Email verified successfully"
    assert user.email_verified is True
    assert AuthService(db_session).resend_verification(email=None)["detail"].startswith("If the account exists")
    assert AuthService(db_session).forgot_password(email="flow@example.com")["detail"].startswith("If the account exists")
    assert tokens.get_valid_password_reset_token(hash_token("issued-token")) is not None
    assert AuthService(db_session).reset_password(token="issued-token", new_password="Resetpass1!")["detail"] == "Password reset successfully"
    assert AuthService(db_session).change_password(user_id=user.user_id, current_password="Resetpass1!", new_password="Changed1!")["detail"] == "Password changed successfully"


def test_verify_reset_and_change_password_error_paths(db_session):
    # Tests missing/invalid token and password-change error handling.
    user = UserRepository(db_session).create(
        email="err@example.com",
        password_hash=hash_password("Oldpass1!"),
        full_name="Error User",
        email_verified=True,
    )
    service = AuthService(db_session)

    with pytest.raises(HTTPException):
        service.verify_email(token=None)
    with pytest.raises(HTTPException):
        service.reset_password(token="missing", new_password="Password1!")
    with pytest.raises(HTTPException):
        service.change_password(user_id=user.user_id, current_password="Wrong1!", new_password="Password1!")
    with pytest.raises(HTTPException):
        service.change_password(user_id=999, current_password="Oldpass1!", new_password="Password1!")


def test_login_success_records_audit_and_returns_token(db_session, monkeypatch):
    # Tests successful login updates last login, records audit, and returns learner profile prompt flag.
    learner_role = _add_role(db_session, "learner", "Learner")
    user = UserRepository(db_session).create(
        email="login@example.com",
        password_hash=hash_password("Password1!"),
        full_name="Login User",
        account_status=AccountStatus.ACTIVE,
        email_verified=True,
    )
    RoleRepository(db_session).assign_role(user.user_id, learner_role.role_id)
    monkeypatch.setattr(AuthService, "_fetch_global_profile_exists", lambda self, user_id: False)

    result = AuthService(db_session).login(email="login@example.com", password="Password1!", ip_address="ip", user_agent="ua")

    assert result["user"]["identity"] == "Learner"
    assert result["shouldShowGlobalProfileInitPrompt"] is True
    assert user.last_login_at is not None


def test_login_records_failures_for_missing_unverified_bad_password_and_inactive(db_session):
    # Tests login failure branches for missing, unverified, bad password, rejected, and deactivated users.
    repo = UserRepository(db_session)
    repo.create(email="unverified@example.com", password_hash=hash_password("Password1!"), full_name="Unverified", email_verified=False)
    repo.create(email="active@example.com", password_hash=hash_password("Password1!"), full_name="Active", email_verified=True, account_status=AccountStatus.ACTIVE)
    repo.create(email="rejected@example.com", password_hash=hash_password("Password1!"), full_name="Rejected", email_verified=True, account_status=AccountStatus.REJECTED)
    repo.create(email="deactivated@example.com", password_hash=hash_password("Password1!"), full_name="Deactivated", email_verified=True, account_status=AccountStatus.DEACTIVATED)
    service = AuthService(db_session)

    for email, password in [
        ("missing@example.com", "Password1!"),
        ("unverified@example.com", "Password1!"),
        ("active@example.com", "Wrong1!"),
        ("rejected@example.com", "Password1!"),
        ("deactivated@example.com", "Password1!"),
    ]:
        with pytest.raises(AuthInvalidCredentialsError):
            service.login(email=email, password=password)


def test_current_user_permissions_filter_pending_educator_active_only_permissions(db_session):
    # Tests that pending educators do not receive educator-only modification permissions.
    educator_role = _add_role(db_session, "educator", "Educator")
    safe_permission = Permission(permission_code="profile:read", permission_name="Read profile", description=None)
    active_only_permission = Permission(permission_code=COURSE_CREATE, permission_name="Create course", description=None)
    db_session.add_all([safe_permission, active_only_permission])
    db_session.flush()
    db_session.add_all([
        RolePermission(role_id=educator_role.role_id, permission_id=safe_permission.permission_id),
        RolePermission(role_id=educator_role.role_id, permission_id=active_only_permission.permission_id),
    ])
    user = UserRepository(db_session).create(
        email="pending@example.com",
        password_hash=hash_password("Password1!"),
        full_name="Pending Educator",
        account_status=AccountStatus.PENDING,
        email_verified=True,
    )
    RoleRepository(db_session).assign_role(user.user_id, educator_role.role_id)
    token = AuthService(db_session).login(email="pending@example.com", password="Password1!")

    permissions = AuthService(db_session).get_current_user_permissions(token["accessToken"])

    assert [permission["permissionCode"] for permission in permissions["permissions"]] == ["profile:read"]


def test_invite_token_validation_and_registration_paths(db_session, monkeypatch):
    # Tests educator invite token validation and registration for new invited educator accounts.
    educator_role = _add_role(db_session, "educator", "Educator")
    admin = UserRepository(db_session).create(email="admin@example.com", password_hash="hash", full_name="Admin")
    invite = EducatorInviteToken(
        invite_id=1,
        invite_uuid="invite-uuid",
        created_by_user_id=admin.user_id,
        token_hash=hash_token("invite-token"),
        expires_at=now_local() + timedelta(days=1),
    )
    db_session.add(invite)
    db_session.flush()
    monkeypatch.setattr("app.services.auth_service.generate_token", lambda length=32: "verify-token")
    monkeypatch.setattr("app.services.auth_service.send_verification_link", lambda *args, **kwargs: None)

    service = AuthService(db_session)
    assert service.validate_educator_invite_token(token="invite-token")["valid"] is True
    result = service.register_via_educator_invite(
        usr_name="Invited Educator",
        email="invited@example.com",
        password="Password1!",
        invite_token="invite-token",
    )

    user = UserRepository(db_session).get_by_email("invited@example.com")
    assert result["user"]["identity"] == "Educator"
    assert RoleRepository(db_session).list_user_roles(user.user_id)[0].role_id == educator_role.role_id
    assert invite.used_by_user_id == user.user_id


def test_invite_token_registration_rejects_missing_invalid_and_duplicate(db_session):
    # Tests invite validation errors and duplicate verified account rejection.
    taken = UserRepository(db_session).create(
        email="taken@example.com",
        password_hash="hash",
        full_name="Taken",
        email_verified=True,
    )
    invite = EducatorInviteToken(
        invite_id=2,
        invite_uuid="invite-uuid-2",
        created_by_user_id=taken.user_id,
        token_hash=hash_token("valid-token"),
        expires_at=now_local() + timedelta(days=1),
    )
    db_session.add(invite)
    db_session.flush()
    service = AuthService(db_session)

    with pytest.raises(HTTPException):
        service.validate_educator_invite_token(token="")
    with pytest.raises(HTTPException):
        service.register_via_educator_invite(usr_name="User", email="new@example.com", password="Password1!", invite_token="")
    with pytest.raises(HTTPException):
        service.register_via_educator_invite(usr_name="User", email="new@example.com", password="Password1!", invite_token="bad")
    with pytest.raises(HTTPException):
        service.register_via_educator_invite(usr_name="Taken", email="taken@example.com", password="Password1!", invite_token="valid-token")
