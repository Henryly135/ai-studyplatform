import pytest
from types import SimpleNamespace

from app.models.user import AccountStatus
from app.services.auth_service import AuthPendingApprovalError, AuthService


def test_dispatch_educator_approval_notification_enqueues_task(monkeypatch):
    # Tests that active admins receive an educator approval notification task.
    service = AuthService(session=None)
    sent: dict = {}

    monkeypatch.setattr(service.roles, "list_user_ids_by_role_code", lambda role_code: [10, 11])
    monkeypatch.setattr(
        service.users,
        "list_by_ids",
        lambda user_ids: [
            SimpleNamespace(
                user_id=10,
                email="admin1@example.com",
                full_name="Admin One",
                account_status=AccountStatus.ACTIVE,
            ),
            SimpleNamespace(
                user_id=11,
                email="admin2@example.com",
                full_name="Admin Two",
                account_status=AccountStatus.ACTIVE,
            ),
        ],
    )
    monkeypatch.setattr(
        "app.services.auth_service.celery_app.send_task",
        lambda name, args, queue: sent.update({"name": name, "args": args, "queue": queue}),
    )

    service._dispatch_educator_approval_notification(
        user=SimpleNamespace(user_id=7, email="teacher@example.com", full_name="Teacher T"),
        request_id=22,
    )

    assert sent["name"] == "app.tasks.notifications.dispatch_educator_approval_request_created_task"
    assert sent["queue"] == "communication.notifications"
    assert sent["args"][0]["actorUserId"] == 7
    assert len(sent["args"][0]["recipients"]) == 2


def test_dispatch_educator_approval_notification_skips_when_no_active_admins(monkeypatch):
    # Tests that notification dispatch is skipped when no active admin recipients exist.
    service = AuthService(session=None)
    called = {"send": False}

    monkeypatch.setattr(service.roles, "list_user_ids_by_role_code", lambda role_code: [10])
    monkeypatch.setattr(
        service.users,
        "list_by_ids",
        lambda user_ids: [
            SimpleNamespace(
                user_id=10,
                email="admin@example.com",
                full_name="Inactive Admin",
                account_status=AccountStatus.DEACTIVATED,
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.auth_service.celery_app.send_task",
        lambda *args, **kwargs: called.update({"send": True}),
    )

    service._dispatch_educator_approval_notification(
        user=SimpleNamespace(user_id=7, email="teacher@example.com", full_name="Teacher T"),
        request_id=22,
    )

    assert called["send"] is False


def test_register_rejects_existing_pending_educator(monkeypatch):
    # Tests that an existing pending educator cannot submit duplicate registration.
    service = AuthService(session=None)
    existing_user = SimpleNamespace(
        user_id=42,
        email="educator@example.com",
        full_name="Pending Educator",
        email_verified=False,
        account_status=AccountStatus.PENDING,
    )

    monkeypatch.setattr(service.users, "get_by_email", lambda email: existing_user)
    monkeypatch.setattr(
        service.roles,
        "list_user_roles",
        lambda user_id: [SimpleNamespace(role_code="educator")],
    )
    monkeypatch.setattr(
        service.approvals,
        "get_pending_request_by_user_id",
        lambda user_id: SimpleNamespace(request_id=99),
    )

    with pytest.raises(AuthPendingApprovalError):
        service.register(
            usr_name="Pending Educator",
            email="educator@example.com",
            password="Password1!",
            identity="Educator",
        )


def test_register_repairs_missing_pending_request_for_existing_educator(monkeypatch):
    # Tests that a pending educator without a request gets one recreated before rejection.
    session = SimpleNamespace(commit=lambda: None)
    service = AuthService(session=session)
    existing_user = SimpleNamespace(
        user_id=42,
        email="educator@example.com",
        full_name="Pending Educator",
        email_verified=False,
        account_status=AccountStatus.PENDING,
    )
    state = {"created": False, "dispatched": False, "committed": False}

    monkeypatch.setattr(service.users, "get_by_email", lambda email: existing_user)
    monkeypatch.setattr(
        service.roles,
        "list_user_roles",
        lambda user_id: [SimpleNamespace(role_code="educator")],
    )
    monkeypatch.setattr(
        service.approvals,
        "get_pending_request_by_user_id",
        lambda user_id: None,
    )
    monkeypatch.setattr(
        service.approvals,
        "create_request",
        lambda user_id: state.update({"created": True}) or SimpleNamespace(request_id=88),
    )
    monkeypatch.setattr(service.session, "commit", lambda: state.update({"committed": True}))
    monkeypatch.setattr(
        service,
        "_dispatch_educator_approval_notification",
        lambda **kwargs: state.update({"dispatched": True}),
    )

    with pytest.raises(AuthPendingApprovalError):
        service.register(
            usr_name="Pending Educator",
            email="educator@example.com",
            password="Password1!",
            identity="Educator",
        )

    assert state == {"created": True, "dispatched": True, "committed": True}
