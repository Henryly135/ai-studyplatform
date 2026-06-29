from __future__ import annotations

from app.core.config import settings
from platform_common.ids.codec import decode_public_uuid, encode_public_uuid
from platform_common.ids.secret import get_public_id_secret


def _get_secret() -> bytes:
    secret = get_public_id_secret(settings.public_id_secret)
    return secret.encode("utf-8")


def _get_secret_text() -> str:
    return _get_secret().decode("utf-8")


def encode_session_uuid(session_id: int) -> str:
    return encode_public_uuid(kind="session", resource_id=session_id, secret=_get_secret_text())


def decode_session_uuid(session_uuid: str) -> int:
    return decode_public_uuid(public_id=session_uuid, expected_kind="session", secret=_get_secret_text())


def encode_course_uuid(course_id: int) -> str:
    return encode_public_uuid(kind="course", resource_id=course_id, secret=_get_secret_text())


def decode_course_uuid(course_uuid: str) -> int:
    return decode_public_uuid(public_id=course_uuid, expected_kind="course", secret=_get_secret_text())


def encode_module_uuid(module_id: int) -> str:
    return encode_public_uuid(kind="module", resource_id=module_id, secret=_get_secret_text())


def decode_module_uuid(module_uuid: str) -> int:
    return decode_public_uuid(public_id=module_uuid, expected_kind="module", secret=_get_secret_text())
