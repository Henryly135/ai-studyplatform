from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.core import email as email_module
from app.core.deps import parse_bearer_token, require_access_token, require_permission
from app.core.public_url import (
    PublicFrontendUrlNotConfiguredError,
    configured_public_frontend_base_url,
    normalize_public_frontend_base_url,
    resolve_public_frontend_base_url,
    resolve_trusted_public_frontend_base_url,
)
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_token,
    hash_password,
    hash_token,
    password_hash_needs_upgrade,
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


class _FailingSMTP(_FakeSMTP):
    def send_message(self, msg):
        raise RuntimeError("smtp secret should not appear")


class _FakeRequest:
    def __init__(self, headers=None, scheme="http"):
        self.headers = headers or {}
        self.url = SimpleNamespace(scheme=scheme)


def test_password_hash_round_trip_and_negative_match():
    # Tests that password hashing accepts the original password and rejects a different one.
    password_hash = hash_password("Password1!")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("Password1!", password_hash) is True
    assert verify_password("WrongPassword1!", password_hash) is False
    assert password_hash_needs_upgrade(password_hash) is False


def test_password_hash_accepts_legacy_sha256_and_marks_for_upgrade():
    # Tests that existing SHA-256 hashes still verify but are scheduled for upgrade.
    legacy_hash = "5785264f6d90120c8f35637046e34725c7ad048547f3665392a745283d8fd528"

    assert verify_password("Eduadmin123!", legacy_hash) is True
    assert verify_password("WrongPassword1!", legacy_hash) is False
    assert password_hash_needs_upgrade(legacy_hash) is True


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


def test_public_url_trusted_base_prefers_configured_frontend(monkeypatch):
    # Tests trusted frontend links use server configuration instead of caller-supplied headers.
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "https://app.example/")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example/api")
    request = _FakeRequest(headers={"origin": "https://evil.example"})

    assert configured_public_frontend_base_url() == "https://app.example"
    assert resolve_trusted_public_frontend_base_url(request) == "https://app.example"


def test_public_url_trusted_base_uses_public_base_without_api(monkeypatch):
    # Tests PUBLIC_BASE_URL can derive the frontend base when PUBLIC_FRONTEND_URL is absent.
    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.example/api")

    assert configured_public_frontend_base_url() == "https://app.example"


def test_public_url_trusted_base_fails_closed_in_production(monkeypatch):
    # Tests production does not trust request headers when the frontend base is not configured.
    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    request = _FakeRequest(headers={"origin": "https://evil.example"})

    with pytest.raises(PublicFrontendUrlNotConfiguredError):
        resolve_trusted_public_frontend_base_url(request)


def test_email_link_builders_use_frontend_base_url():
    # Tests that verification and reset links target the frontend routes with encoded tokens.
    assert email_module.build_verify_link("a b", "http://ui.test/") == "http://ui.test/verify-email?token=a+b"
    assert email_module.build_reset_link("r+t", "http://ui.test") == "http://ui.test/reset-password?token=r%2Bt"


def test_email_link_builders_use_configured_frontend_base(monkeypatch):
    # Tests email link builders share the trusted configured frontend base rules.
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "https://app.example/")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example/api")

    assert email_module.build_verify_link("tok") == "https://app.example/verify-email?token=tok"

    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)

    assert email_module.build_reset_link("tok") == "https://api.example/reset-password?token=tok"


def test_email_link_builders_fail_closed_in_production_without_config(monkeypatch):
    # Tests production never generates verification/reset links using localhost fallback.
    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("NGINX_PORT", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(PublicFrontendUrlNotConfiguredError):
        email_module.build_verify_link("tok")
    with pytest.raises(PublicFrontendUrlNotConfiguredError):
        email_module.build_reset_link("tok")


def test_email_senders_use_smtp_when_configured(monkeypatch, capsys):
    # Tests that verification, reset, and invite emails are delivered through configured SMTP.
    _FakeSMTP.sent_messages = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "from@example.com")
    monkeypatch.setattr(email_module.smtplib, "SMTP", _FakeSMTP)

    results = [
        email_module.send_verification_link("to@example.com", "tok", frontend_base_url="http://ui"),
        email_module.send_password_reset_link("to@example.com", "tok", frontend_base_url="http://ui"),
        email_module.send_educator_invite_email("to@example.com", "http://ui/register"),
    ]

    assert all(result.attempted and result.delivered for result in results)
    assert [msg["To"] for msg in _FakeSMTP.sent_messages] == ["to@example.com"] * 3
    assert _FakeSMTP.sent_messages[0]["Subject"] == "Verify your email"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_email_senders_skip_unconfigured_smtp_without_printing_links(monkeypatch, capsys, caplog):
    # Tests that dev-mode email links are not printed or logged when SMTP is disabled.
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    caplog.set_level("INFO", logger=email_module.__name__)

    result = email_module.send_verification_link(
        "to@example.com",
        "secret-token",
        frontend_base_url="http://ui",
    )

    assert result == email_module.EmailDeliveryResult(
        attempted=False,
        delivered=False,
        reason="smtp_not_configured",
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert "secret-token" not in caplog.text
    assert "verify-email" not in caplog.text
    assert "to@example.com" not in caplog.text


def test_email_senders_report_smtp_failure_without_logging_sensitive_payload(monkeypatch, capsys, caplog):
    # Tests that SMTP failures are observable without exposing reset tokens or recipient emails.
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "from@example.com")
    monkeypatch.setattr(email_module.smtplib, "SMTP", _FailingSMTP)
    caplog.set_level("WARNING", logger=email_module.__name__)

    result = email_module.send_password_reset_link(
        "to@example.com",
        "reset-secret-token",
        frontend_base_url="http://ui",
    )

    assert result == email_module.EmailDeliveryResult(
        attempted=True,
        delivered=False,
        reason="smtp_error:RuntimeError",
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert "reset-secret-token" not in caplog.text
    assert "reset-password" not in caplog.text
    assert "to@example.com" not in caplog.text
    assert "smtp secret should not appear" not in caplog.text


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
