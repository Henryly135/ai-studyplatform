from platform_common.ids.codec import decode_public_uuid, encode_public_uuid
from platform_common.ids.secret import get_public_id_secret

from app.core.config import settings


def _get_secret() -> str:
    return get_public_id_secret(settings.public_id_secret)


def encode_user_uuid(user_id: int) -> str:
    return encode_public_uuid(kind="user", resource_id=user_id, secret=_get_secret())


def decode_user_uuid(user_uuid: str) -> int:
    return decode_public_uuid(public_id=user_uuid, expected_kind="user", secret=_get_secret())


def encode_request_uuid(request_id: int) -> str:
    return encode_public_uuid(kind="request", resource_id=request_id, secret=_get_secret())


def decode_request_uuid(request_uuid: str) -> int:
    return decode_public_uuid(public_id=request_uuid, expected_kind="request", secret=_get_secret())
