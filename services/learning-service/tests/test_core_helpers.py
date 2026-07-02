from types import SimpleNamespace

import pytest

from app.core.public_url import (
    PublicFrontendUrlNotConfiguredError,
    configured_public_frontend_base_url,
    normalize_public_frontend_base_url,
    resolve_public_frontend_base_url,
    resolve_trusted_public_frontend_base_url,
)
from app.core.time import now_local
from app.core.uuid_codec import (
    decode_course_uuid,
    decode_material_uuid,
    decode_module_uuid,
    decode_quiz_attempt_uuid,
    decode_quiz_option_uuid,
    decode_quiz_question_uuid,
    decode_quiz_uuid,
    decode_user_uuid,
    encode_course_uuid,
    encode_material_uuid,
    encode_module_uuid,
    encode_quiz_attempt_uuid,
    encode_quiz_option_uuid,
    encode_quiz_question_uuid,
    encode_quiz_uuid,
    encode_user_uuid,
)


class _FakeRequest:
    def __init__(self, headers=None, scheme="http"):
        self.headers = headers or {}
        self.url = SimpleNamespace(scheme=scheme)


def test_uuid_codecs_round_trip_all_learning_public_ids():
    # Tests that every learning public UUID codec can recover the original numeric id.
    pairs = [
        (encode_course_uuid, decode_course_uuid),
        (encode_module_uuid, decode_module_uuid),
        (encode_material_uuid, decode_material_uuid),
        (encode_quiz_uuid, decode_quiz_uuid),
        (encode_quiz_question_uuid, decode_quiz_question_uuid),
        (encode_quiz_option_uuid, decode_quiz_option_uuid),
        (encode_quiz_attempt_uuid, decode_quiz_attempt_uuid),
        (encode_user_uuid, decode_user_uuid),
    ]

    for index, (encoder, decoder) in enumerate(pairs, start=1):
        assert decoder(encoder(index)) == index


def test_public_url_normalizes_localhost_ip_and_passthrough_hosts(monkeypatch):
    # Tests public frontend URL normalization for localhost, IP hosts, and external hostnames.
    monkeypatch.setenv("PUBLIC_FRONTEND_PORT", "3000")

    assert normalize_public_frontend_base_url("http://localhost") == "http://localhost:3000"
    assert normalize_public_frontend_base_url("http://127.0.0.1") == "http://127.0.0.1:3000"
    assert normalize_public_frontend_base_url("https://app.example") == "https://app.example"
    assert normalize_public_frontend_base_url("  ") is None


def test_public_url_resolves_headers_in_priority_order(monkeypatch):
    # Tests explicit frontend, origin, and forwarded host URL resolution order.
    monkeypatch.setenv("PUBLIC_FRONTEND_PORT", "4000")

    explicit = _FakeRequest(headers={"x-public-frontend-url": "http://localhost", "origin": "https://ignored"})
    origin = _FakeRequest(headers={"origin": "https://app.example"})
    forwarded = _FakeRequest(headers={"x-forwarded-proto": "https", "x-forwarded-host": "localhost"})

    assert resolve_public_frontend_base_url(explicit) == "http://localhost:4000"
    assert resolve_public_frontend_base_url(origin) == "https://app.example"
    assert resolve_public_frontend_base_url(forwarded) == "https://localhost:4000"


def test_public_url_trusted_base_prefers_configured_frontend(monkeypatch):
    # Tests trusted frontend URLs use server configuration instead of request headers.
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
    # Tests production does not trust request headers for public invite links.
    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    request = _FakeRequest(headers={"origin": "https://evil.example"})

    with pytest.raises(PublicFrontendUrlNotConfiguredError):
        resolve_trusted_public_frontend_base_url(request)


def test_now_local_returns_datetime_value():
    # Tests that the learning service time helper returns a datetime-like value.
    assert now_local().year >= 2024
