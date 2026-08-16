from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastapi import Response

from app.services import material_access_session as session_module


def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        session_module,
        "settings",
        SimpleNamespace(
            public_id_secret="test-public-id-secret-for-material-session",
            material_access_url_expires_seconds=300,
        ),
    )


def test_material_access_session_is_bound_to_authenticated_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    token = session_module.create_material_access_session(user_id=7, identity="Learner")

    grant = session_module.validate_material_access_session(token)

    assert grant.user_id == 7
    assert grant.identity == "Learner"
    with pytest.raises(ValueError):
        session_module.require_matching_material_access_session(
            token=token,
            user_id=8,
            identity="Learner",
        )


def test_expired_material_access_session_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    token = session_module.create_material_access_session(
        user_id=7,
        identity="Learner",
        expires_at=int(time.time()) - 1,
    )

    with pytest.raises(ValueError):
        session_module.validate_material_access_session(token)


def test_authenticated_learning_response_sets_http_only_material_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch)
    response = Response()

    session_module.set_material_access_session_cookie(
        response,
        {"id": 7, "identity": "Learner"},
    )

    cookie_header = response.headers["set-cookie"]
    assert session_module.MATERIAL_ACCESS_SESSION_COOKIE in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=strict" in cookie_header
