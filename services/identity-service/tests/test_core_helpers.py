from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.core import email as email_module
from app.core.deps import parse_bearer_token, require_access_token, require_permission
from app.core.public_url import normalize_public_frontend_base_url, resolve_public_frontend_base_url
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.uuid_codec import decode_request_uuid, decode_user_uuid, encode_request_uuid, encode_user_uuid
from app.services.auth_service import AuthInvalidCredentialsError


class _FakeSMTP:
    sent_messages = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        return None

    def login(self, user, password):
        return None

    def send_message(self, msg):
        self.sent_messages.append(msg)


class _FakeRequest:
    def __init__(self, headers=None, scheme="http"):
        self.headers = headers or {}
        self.url = SimpleNamespace(scheme=scheme)


def test_password_hash_round_trip_and_negative_match():
    # Tests that password hashing accepts the original password and rejects a different one.
    password_hash = hash_password("Password1!")

    assert verify_password("Password1!", password_hash) is True
    assert verify_password("WrongPassword1!", password_hash) is False


def test_token_helpers_create_hash_and_decode_access_token():
    # Tests random token generation, deterministic token hashing, and JWT decoding.
    raw_token = generate_token(8)
    access_token = create_access_token(12, "Learner", expires_delta=timedelta(minutes=5))

    assert len(raw_token) >= 8
    assert hash_token("abc") == hash_token("abc")
    assert decode_access_token(access_token)["sub"] == "12"


def test_decode_access_token_raises_for_invalid_token():
    # Tests that malformed JWTs are rejected by the decoder.
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-token")


def test_uuid_codec_round_trips_user_and_request_ids():
    # Tests that public UUID codecs can recover encoded user and request ids.
    user_uuid = encode_user_uuid(42)
    request_uuid = encode_request_uuid(77)

    assert decode_user_uuid(user_uuid) == 42
    assert decode_request_uuid(request_uuid) == 77


def test_public_url_normalizes_localhost_with_public_port(monkeypatch):
    # Tests that public frontend URLs append the configured public port for localhost.
    monkeypatch.setenv("PUBLIC_FRONTEND_PORT", "3000")

    assert normalize_public_frontend_base_url("http://localhost") == "http://localhost:3000"


def test_public_url_resolves_explicit_header_before_origin(monkeypatch):
    # Tests that explicit frontend URL headers take precedence over request origin.
    monkeypatch.setenv("PUBLIC_FRONTEND_PORT", "3000")
    request = _FakeRequest(
        headers={
            "x-public-frontend-url": "http://localhost",
            "origin": "https://ignored.example",
        }
    )

    assert resolve_public_frontend_base_url(request) == "http://localhost:3000"


def test_public_url_resolves_forwarded_host_when_origin_missing(monkeypatch):
    # Tests that forwarded proto and host build a public frontend URL when origin is absent.
    monkeypatch.delenv("PUBLIC_FRONTEND_PORT", raising=False)
    request = _FakeRequest(headers={"x-forwarded-proto": "https", "x-forwarded-host": "app.example"})

    assert resolve_public_frontend_base_url(request) == "https://app.example"


def test_email_link_builders_use_frontend_base_url():
    # Tests that verification and reset links target the frontend routes with encoded tokens.
    assert email_module.build_verify_link("a b", "http://ui.test/") == "http://ui.test/verify-email?token=a+b"
    assert email_module.build_reset_link("r+t", "http://ui.test") == "http://ui.test/reset-password?token=r%2Bt"


def test_email_senders_use_smtp_when_configured(monkeypatch):
    # Tests that verification, reset, and invite emails are delivered through configured SMTP.
    _FakeSMTP.sent_messages = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "from@example.com")
    monkeypatch.setattr(email_module.smtplib, "SMTP", _FakeSMTP)

    email_module.send_verification_link("to@example.com", "tok", frontend_base_url="http://ui")
    email_module.send_password_reset_link("to@example.com", "tok", frontend_base_url="http://ui")
    email_module.send_educator_invite_email("to@example.com", "http://ui/register")

    assert [msg["To"] for msg in _FakeSMTP.sent_messages] == ["to@example.com"] * 3
    assert _FakeSMTP.sent_messages[0]["Subject"] == "Verify your email"


def test_approval_result_email_rejects_unknown_result():
    # Tests that approval result emails accept only approved or rejected outcomes.
    with pytest.raises(ValueError):
        email_module.send_educator_approval_result_email("to@example.com", "User", "maybe")


def test_parse_bearer_token_accepts_valid_header_and_rejects_invalid():
    # Tests bearer token parsing success and invalid credential masking.
    assert parse_bearer_token("Bearer abc") == "abc"
    with pytest.raises(HTTPException) as exc_info:
        parse_bearer_token("Basic abc")
    assert exc_info.value.detail == "Invalid credentials"


def test_require_access_token_returns_parsed_token():
    # Tests that the access-token dependency returns the bearer token value.
    assert require_access_token("Bearer token-value") == "token-value"


def test_require_permission_allows_user_with_required_permission(monkeypatch):
    # Tests that permission dependency attaches sorted permissions when access is allowed.
    class FakeAuthService:
        def __init__(self, session):
            self.session = session

        def get_current_user(self, token):
            return {"id": 1}

        def get_current_user_permissions(self, token):
            return {"permissions": [{"permissionCode": "user:read"}, {"permissionCode": "course:update"}]}

    monkeypatch.setattr("app.services.auth_service.AuthService", FakeAuthService)
    dependency = require_permission("user:read")

    result = dependency(token="tok", session=object())

    assert result["permissions"] == ["course:update", "user:read"]


def test_require_permission_converts_auth_errors(monkeypatch):
    # Tests that auth service failures are converted into HTTP exceptions by the permission dependency.
    class FakeAuthService:
        def __init__(self, session):
            pass

        def get_current_user(self, token):
            raise AuthInvalidCredentialsError()

    monkeypatch.setattr("app.services.auth_service.AuthService", FakeAuthService)
    dependency = require_permission("user:read")

    with pytest.raises(HTTPException) as exc_info:
        dependency(token="bad", session=object())

    assert exc_info.value.status_code == 401
