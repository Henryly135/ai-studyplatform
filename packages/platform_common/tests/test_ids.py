import pytest
from fastapi import HTTPException

from platform_common.auth.dependencies import build_require_internal_request
from platform_common.ids.codec import decode_public_uuid, encode_public_uuid


@pytest.mark.parametrize(
    ("kind", "resource_id"),
    [
        ("course", 101),
        ("module", 202),
        ("material", 303),
        ("request", 350),
        ("session", 404),
        ("user", 505),
    ],
)
def test_encode_decode_round_trip(kind: str, resource_id: int) -> None:
    secret = "shared-test-secret"

    public_id = encode_public_uuid(kind=kind, resource_id=resource_id, secret=secret)

    decoded_id = decode_public_uuid(public_id=public_id, expected_kind=kind, secret=secret)

    assert decoded_id == resource_id


@pytest.mark.parametrize(
    ("encoded_kind", "decoded_kind"),
    [
        ("course", "module"),
        ("module", "material"),
        ("material", "request"),
        ("request", "session"),
        ("session", "user"),
        ("user", "course"),
    ],
)
def test_different_kinds_cannot_be_decoded_interchangeably(encoded_kind: str, decoded_kind: str) -> None:
    secret = "shared-test-secret"
    public_id = encode_public_uuid(kind=encoded_kind, resource_id=123, secret=secret)

    with pytest.raises(HTTPException) as exc_info:
        decode_public_uuid(public_id=public_id, expected_kind=decoded_kind, secret=secret)

    assert exc_info.value.status_code == 400


def test_build_require_internal_request_accepts_matching_token() -> None:
    dependency = build_require_internal_request(lambda: "shared-secret")

    assert dependency("shared-secret") is None


def test_build_require_internal_request_rejects_missing_or_wrong_token() -> None:
    dependency = build_require_internal_request(lambda: "shared-secret")

    with pytest.raises(HTTPException) as missing_exc:
        dependency(None)
    assert missing_exc.value.status_code == 403

    with pytest.raises(HTTPException) as wrong_exc:
        dependency("wrong-secret")
    assert wrong_exc.value.status_code == 403


def test_build_require_internal_request_rejects_unconfigured_token() -> None:
    dependency = build_require_internal_request(lambda: "")

    with pytest.raises(HTTPException) as exc:
        dependency("shared-secret")
    assert exc.value.status_code == 503
