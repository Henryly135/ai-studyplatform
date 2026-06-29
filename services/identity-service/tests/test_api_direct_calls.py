from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import admin as admin_api
from app.api import auth as auth_api
from app.api import internal as internal_api
from app.schemas.admin import (
    AdminUserListResponse,
    EducatorApprovalHistoryQuery,
    EducatorApprovalListResponse,
    EducatorApprovalRead,
    EducatorInviteTokenListResponse,
    ReviewEducatorApprovalRequest,
    SendEducatorInviteEmailRequest,
    UpdateUserIdentityRequest,
    UpdateUserStatusRequest,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    EducatorInviteRegisterRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.user_directory import UserDirectoryLookupRequest, UserDirectoryLookupResponse
from app.services.admin_user_service import AdminUserNotFoundError
from app.services.approval_service import EducatorApprovalNotFoundError
from app.services.auth_service import AuthInvalidCredentialsError


class _Request:
    def __init__(self, headers=None, host="127.0.0.1"):
        self.headers = headers or {}
        self.client = SimpleNamespace(host=host)
        self.url = SimpleNamespace(scheme="http")


def _approval_read():
    now = datetime(2024, 1, 1).isoformat()
    return EducatorApprovalRead(
        requestUuid="req",
        requestStatus="pending",
        submittedAt=now,
        updatedAt=now,
        userId=1,
        userUuid="user",
        email="educator@example.com",
        userName="Educator",
        identity="Educator",
        accountStatus="pending",
        emailVerified=True,
    )


def test_auth_register_delegates_to_service(monkeypatch):
    # Tests that register endpoint forwards request data and resolved frontend URL.
    captured = {}

    class FakeAuthService:
        def __init__(self, session):
            pass

        def register(self, **kwargs):
            captured.update(kwargs)
            return {"detail": "ok"}

    monkeypatch.setattr(auth_api, "AuthService", FakeAuthService)

    result = auth_api.register(
        RegisterRequest(userName="User", email="user@example.com", password="Password1!", identity="Learner"),
        _Request(headers={"origin": "http://frontend"}),
        session=object(),
    )

    assert result == {"detail": "ok"}
    assert captured["email"] == "user@example.com"
    assert captured["public_frontend_base_url"] == "http://frontend"


def test_auth_login_uses_forwarded_ip_and_converts_service_errors(monkeypatch):
    # Tests login endpoint IP extraction and AuthServiceError to HTTPException conversion.
    captured = {}

    class FakeAuthService:
        def __init__(self, session):
            pass

        def login(self, **kwargs):
            captured.update(kwargs)
            raise AuthInvalidCredentialsError("bad")

    monkeypatch.setattr(auth_api, "AuthService", FakeAuthService)

    with pytest.raises(HTTPException) as exc_info:
        auth_api.login(
            LoginRequest(email="user@example.com", password="Password1!"),
            _Request(headers={"x-forwarded-for": "10.0.0.1, 10.0.0.2", "user-agent": "pytest"}),
            session=object(),
        )

    assert captured["ip_address"] == "10.0.0.1"
    assert exc_info.value.status_code == 401


def test_auth_simple_endpoints_delegate_to_service(monkeypatch):
    # Tests verify, resend, forgot, reset, permissions, change-password, and invite auth endpoints.
    calls = []

    class FakeAuthService:
        def __init__(self, session):
            pass

        def verify_email(self, **kwargs):
            calls.append(("verify", kwargs))
            return {"detail": "verified"}

        def resend_verification(self, **kwargs):
            calls.append(("resend", kwargs))
            return {"detail": "resent"}

        def forgot_password(self, **kwargs):
            calls.append(("forgot", kwargs))
            return {"detail": "forgot"}

        def reset_password(self, **kwargs):
            calls.append(("reset", kwargs))
            return {"detail": "reset"}

        def get_current_user_permissions(self, token):
            calls.append(("permissions", token))
            return {"permissions": []}

        def change_password(self, **kwargs):
            calls.append(("change", kwargs))
            return {"detail": "changed"}

        def validate_educator_invite_token(self, **kwargs):
            calls.append(("validate", kwargs))
            return {"valid": True}

        def register_via_educator_invite(self, **kwargs):
            calls.append(("invite", kwargs))
            return {"detail": "invited"}

    monkeypatch.setattr(auth_api, "AuthService", FakeAuthService)

    assert auth_api.verify_email(token="tok", session=object())["detail"] == "verified"
    assert auth_api.resend_verification({"email": "user@example.com"}, _Request(headers={"origin": "http://ui"}), object())["detail"] == "resent"
    assert auth_api.me({"id": 1}) == {"id": 1}
    assert auth_api.forgot_password(ForgotPasswordRequest(email="user@example.com"), _Request(), object())["detail"] == "forgot"
    assert auth_api.reset_password(ResetPasswordRequest(token="tok", newPassword="Password1!"), object())["detail"] == "reset"
    assert auth_api.me_permissions({}, token="tok", session=object()) == {"permissions": []}
    assert auth_api.change_password(ChangePasswordRequest(currentPassword="Old1!", newPassword="Newpass1!"), {"id": 4}, object())["detail"] == "changed"
    assert auth_api.validate_educator_invite(token="tok", session=object()) == {"valid": True}
    assert auth_api.register_educator_invite(
        EducatorInviteRegisterRequest(userName="Ed", email="ed@example.com", password="Password1!", inviteToken="tok"),
        _Request(),
        object(),
    )["detail"] == "invited"
    assert [call[0] for call in calls] == ["verify", "resend", "forgot", "reset", "permissions", "change", "validate", "invite"]


def test_admin_invite_url_uses_frontend_public_base(monkeypatch):
    # Tests invite URL building from explicit frontend base and environment fallbacks.
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "http://env-ui/")

    assert admin_api._build_invite_url("a b", frontend_base_url="http://ui/") == "http://ui/register/educator-invite?token=a+b"
    assert admin_api._build_invite_url("tok") == "http://env-ui/register/educator-invite?token=tok"


def test_admin_user_endpoints_delegate_and_convert_errors(monkeypatch):
    # Tests admin user endpoints delegate to service and convert service errors.
    class FakeAdminUserService:
        def __init__(self, session):
            pass

        def list_users(self):
            return AdminUserListResponse(users=[])

        def update_user_identity(self, **kwargs):
            raise AdminUserNotFoundError()

        def update_user_status(self, **kwargs):
            raise AdminUserNotFoundError()

    monkeypatch.setattr(admin_api, "AdminUserService", FakeAdminUserService)

    assert admin_api.list_users(current_user={"id": 1}, session=object()).users == []
    with pytest.raises(HTTPException) as identity_exc:
        admin_api.update_user_identity("uuid", UpdateUserIdentityRequest(identity="Learner"), {"id": 1}, object())
    with pytest.raises(HTTPException) as status_exc:
        admin_api.update_user_status("uuid", UpdateUserStatusRequest(accountStatus="active"), {"id": 1}, object())

    assert identity_exc.value.status_code == 404
    assert status_exc.value.status_code == 404


def test_admin_approval_endpoints_delegate_and_convert_errors(monkeypatch):
    # Tests admin approval endpoints delegate to approval service and map service errors.
    class FakeApprovalService:
        def __init__(self, session):
            pass

        def list_requests(self):
            return EducatorApprovalListResponse(requests=[])

        def list_reviewed_requests(self, **kwargs):
            return EducatorApprovalListResponse(requests=[])

        def get_request_by_uuid(self, request_uuid):
            raise EducatorApprovalNotFoundError()

        def review_request_by_uuid(self, **kwargs):
            raise EducatorApprovalNotFoundError()

    monkeypatch.setattr(admin_api, "ApprovalService", FakeApprovalService)

    assert admin_api.list_educator_approvals(current_user={"id": 1}, session=object()).requests == []
    assert admin_api.list_reviewed_educator_approvals(
        query=EducatorApprovalHistoryQuery(status="reviewed"),
        current_user={"id": 1},
        session=object(),
    ).requests == []
    with pytest.raises(HTTPException) as get_exc:
        admin_api.get_educator_approval("req", {"id": 1}, object())
    with pytest.raises(HTTPException) as review_exc:
        admin_api.review_educator_approval("req", ReviewEducatorApprovalRequest(action="approve"), {"id": 1}, object())

    assert get_exc.value.status_code == 404
    assert review_exc.value.status_code == 404


def test_admin_invite_token_endpoints_generate_send_and_list(monkeypatch):
    # Tests invite token generation, send-email guard branches, and list serialization.
    class FakeAuthService:
        def __init__(self, session):
            pass

        def generate_educator_invite_token(self, **kwargs):
            return {"inviteUuid": "invite-1", "rawToken": "raw", "expiresAt": "2024-01-02T00:00:00"}

    class FakeRepo:
        token = SimpleNamespace(
            created_by_user_id=1,
            used_at=None,
            invite_uuid="invite-1",
            created_at=datetime(2024, 1, 1),
            expires_at=datetime.now() + timedelta(days=1),
        )

        def __init__(self, session):
            pass

        def get_by_uuid(self, invite_uuid):
            return self.token

        def list_by_creator(self, creator_id):
            return [self.token]

    sent = {}
    monkeypatch.setattr(admin_api, "AuthService", FakeAuthService)
    monkeypatch.setattr(admin_api, "EducatorInviteTokenRepository", FakeRepo)
    monkeypatch.setattr("app.repositories.educator_invite_token_repository.EducatorInviteTokenRepository", FakeRepo)
    monkeypatch.setattr("app.core.email.send_educator_invite_email", lambda email, url: sent.update({"email": email, "url": url}))

    generated = admin_api.generate_educator_invite_token(_Request(headers={"origin": "http://ui"}), {"id": 1}, object())
    assert generated.inviteUrl == "http://ui/register/educator-invite?token=raw"

    response = admin_api.send_educator_invite_email_endpoint(
        "invite-1",
        SendEducatorInviteEmailRequest(recipientEmail="ed@example.com", inviteUrl="http://ui/invite"),
        {"id": 1},
        object(),
    )
    assert response == {"detail": "Invite email sent"}
    assert sent["email"] == "ed@example.com"

    listed = admin_api.list_educator_invite_tokens({"id": 1}, object())
    assert isinstance(listed, EducatorInviteTokenListResponse)
    assert listed.tokens[0].inviteUuid == "invite-1"


def test_admin_invite_email_rejects_missing_wrong_owner_and_used_tokens(monkeypatch):
    # Tests invite-email endpoint error branches for missing, unauthorized, and used tokens.
    class FakeRepo:
        token = None

        def __init__(self, session):
            pass

        def get_by_uuid(self, invite_uuid):
            return self.token

    monkeypatch.setattr(admin_api, "EducatorInviteTokenRepository", FakeRepo)
    monkeypatch.setattr("app.repositories.educator_invite_token_repository.EducatorInviteTokenRepository", FakeRepo)

    with pytest.raises(HTTPException) as missing_exc:
        admin_api.send_educator_invite_email_endpoint("missing", SendEducatorInviteEmailRequest(recipientEmail="ed@example.com", inviteUrl="http://ui"), {"id": 1}, object())
    assert missing_exc.value.status_code == 404

    FakeRepo.token = SimpleNamespace(created_by_user_id=2, used_at=None)
    with pytest.raises(HTTPException) as owner_exc:
        admin_api.send_educator_invite_email_endpoint("invite", SendEducatorInviteEmailRequest(recipientEmail="ed@example.com", inviteUrl="http://ui"), {"id": 1}, object())
    assert owner_exc.value.status_code == 403

    FakeRepo.token = SimpleNamespace(created_by_user_id=1, used_at=datetime.now())
    with pytest.raises(HTTPException) as used_exc:
        admin_api.send_educator_invite_email_endpoint("invite", SendEducatorInviteEmailRequest(recipientEmail="ed@example.com", inviteUrl="http://ui"), {"id": 1}, object())
    assert used_exc.value.status_code == 409


def test_internal_lookup_users_delegates_to_directory_service(monkeypatch):
    # Tests that the internal user lookup endpoint forwards ids to the directory service.
    class FakeDirectoryService:
        def __init__(self, session):
            pass

        def lookup_users_by_ids(self, **kwargs):
            return UserDirectoryLookupResponse(users=[])

    monkeypatch.setattr(internal_api, "UserDirectoryService", FakeDirectoryService)

    result = internal_api.lookup_users(UserDirectoryLookupRequest(userIds=[1, 2]), session=object())

    assert result.users == []
