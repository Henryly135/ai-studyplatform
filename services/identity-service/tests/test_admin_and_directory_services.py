from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.uuid_codec import encode_user_uuid
from app.models.user import AccountStatus
from app.services.admin_user_service import (
    AdminUserNotFoundError,
    AdminUserService,
    InvalidAccountStatusError,
    InvalidUserIdentityError,
    NoUserChangeRequiredError,
    ProtectedUserUpdateError,
    RoleConfigurationError,
)
from app.services.user_directory_service import UserDirectoryService


def _user(user_id=1, status=AccountStatus.ACTIVE, verified=True):
    now = datetime(2024, 1, 1, 12, 0, 0)
    return SimpleNamespace(
        user_id=user_id,
        email=f"user{user_id}@example.com",
        full_name=f"User {user_id}",
        account_status=status,
        email_verified=verified,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


def test_admin_user_list_excludes_admin_accounts(monkeypatch):
    # Tests that admin user listing hides accounts carrying the admin role.
    service = AdminUserService(session=SimpleNamespace())
    users = [_user(1), _user(2)]

    monkeypatch.setattr(service.users, "list_all", lambda: users)
    monkeypatch.setattr(
        service.roles,
        "list_user_roles",
        lambda user_id: [SimpleNamespace(role_code="admin")] if user_id == 2 else [SimpleNamespace(role_code="learner")],
    )

    result = service.list_users()

    assert [user.id for user in result.users] == [1]


def test_update_user_identity_changes_role_and_writes_audit(monkeypatch):
    # Tests that changing a user's identity replaces roles and records an audit log.
    session = SimpleNamespace(commit=lambda: None, refresh=lambda obj: None)
    service = AdminUserService(session=session)
    target = _user(5)
    current_role = SimpleNamespace(role_id=1, role_code="learner")
    educator_role = SimpleNamespace(role_id=2, role_code="educator")
    calls = {}

    monkeypatch.setattr(service.users, "get_by_id", lambda user_id: target)
    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [current_role])
    monkeypatch.setattr(service.roles, "get_by_code", lambda role_code: educator_role)
    monkeypatch.setattr(service.roles, "clear_user_roles", lambda user_id: calls.update({"cleared": user_id}))
    monkeypatch.setattr(service.roles, "assign_role", lambda user_id, role_id: calls.update({"assigned": (user_id, role_id)}))
    monkeypatch.setattr(service.audit_logs, "create_user_role_audit_log", lambda **kwargs: calls.update({"audit": kwargs}))

    result = service.update_user_identity(user_uuid=encode_user_uuid(5), identity=" educator ", changed_by_user_id=99)

    assert result.id == 5
    assert calls["cleared"] == 5
    assert calls["assigned"] == (5, 2)
    assert calls["audit"]["changed_by"] == 99


def test_update_user_identity_rejects_invalid_and_protected_cases(monkeypatch):
    # Tests invalid identity, missing user, admin-protected, missing-role, and no-change branches.
    service = AdminUserService(session=SimpleNamespace())

    with pytest.raises(InvalidUserIdentityError):
        service.update_user_identity(user_uuid=encode_user_uuid(1), identity="Admin", changed_by_user_id=1)

    monkeypatch.setattr(service.users, "get_by_id", lambda user_id: None)
    with pytest.raises(AdminUserNotFoundError):
        service.update_user_identity(user_uuid=encode_user_uuid(1), identity="Learner", changed_by_user_id=1)

    monkeypatch.setattr(service.users, "get_by_id", lambda user_id: _user(1))
    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [SimpleNamespace(role_id=3, role_code="admin")])
    with pytest.raises(ProtectedUserUpdateError):
        service.update_user_identity(user_uuid=encode_user_uuid(1), identity="Learner", changed_by_user_id=1)

    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [SimpleNamespace(role_id=1, role_code="learner")])
    monkeypatch.setattr(service.roles, "get_by_code", lambda role_code: None)
    with pytest.raises(RoleConfigurationError):
        service.update_user_identity(user_uuid=encode_user_uuid(1), identity="Educator", changed_by_user_id=1)

    monkeypatch.setattr(service.roles, "get_by_code", lambda role_code: SimpleNamespace(role_id=1, role_code="learner"))
    with pytest.raises(NoUserChangeRequiredError):
        service.update_user_identity(user_uuid=encode_user_uuid(1), identity="Learner", changed_by_user_id=1)


def test_update_user_status_changes_status_and_writes_audit(monkeypatch):
    # Tests that account-status changes update the user and record an audit log.
    session = SimpleNamespace(commit=lambda: None, refresh=lambda obj: None)
    service = AdminUserService(session=session)
    target = _user(5, status=AccountStatus.PENDING)
    learner_role = SimpleNamespace(role_id=1, role_code="learner")
    calls = {}

    monkeypatch.setattr(service.users, "get_by_id", lambda user_id: target)
    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [learner_role])
    monkeypatch.setattr(service.users, "update_account_status", lambda user, status: setattr(user, "account_status", status))
    monkeypatch.setattr(service.audit_logs, "create_user_role_audit_log", lambda **kwargs: calls.update({"audit": kwargs}))

    result = service.update_user_status(user_uuid=encode_user_uuid(5), account_status=" active ", changed_by_user_id=99)

    assert result.accountStatus == "active"
    assert calls["audit"]["change_reason"] == "Account status updated to active"


def test_update_user_status_rejects_invalid_missing_protected_and_no_change(monkeypatch):
    # Tests account-status validation, missing user, admin-protected, and no-change branches.
    service = AdminUserService(session=SimpleNamespace())

    with pytest.raises(InvalidAccountStatusError):
        service.update_user_status(user_uuid=encode_user_uuid(1), account_status="paused", changed_by_user_id=1)

    monkeypatch.setattr(service.users, "get_by_id", lambda user_id: None)
    with pytest.raises(AdminUserNotFoundError):
        service.update_user_status(user_uuid=encode_user_uuid(1), account_status="active", changed_by_user_id=1)

    monkeypatch.setattr(service.users, "get_by_id", lambda user_id: _user(1))
    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [SimpleNamespace(role_code="admin")])
    with pytest.raises(ProtectedUserUpdateError):
        service.update_user_status(user_uuid=encode_user_uuid(1), account_status="deactivated", changed_by_user_id=1)

    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [SimpleNamespace(role_code="learner")])
    with pytest.raises(NoUserChangeRequiredError):
        service.update_user_status(user_uuid=encode_user_uuid(1), account_status="active", changed_by_user_id=1)


def test_user_directory_deduplicates_ids_and_skips_missing_users(monkeypatch):
    # Tests directory lookup preserves unique input order and omits unknown users.
    service = UserDirectoryService(session=SimpleNamespace())
    user = _user(2)
    captured = {}

    monkeypatch.setattr(
        service.users,
        "list_by_ids",
        lambda user_ids: captured.update({"user_ids": user_ids}) or [user],
    )
    monkeypatch.setattr(
        service.roles,
        "list_roles_by_user_ids",
        lambda user_ids: {2: [SimpleNamespace(role_code="educator")]},
    )

    result = service.lookup_users_by_ids(user_ids=[2, 2, 3])

    assert captured["user_ids"] == [2, 3]
    assert len(result.users) == 1
    assert result.users[0].identity == "Educator"
