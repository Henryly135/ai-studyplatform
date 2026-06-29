from platform_common.ids.codec import decode_public_uuid, encode_public_uuid
from platform_common.ids.secret import get_public_id_secret

from app.core.config import settings


def _get_secret() -> str:
    return get_public_id_secret(settings.public_id_secret)


def encode_course_uuid(course_id: int) -> str:
    return encode_public_uuid(kind="course", resource_id=course_id, secret=_get_secret())


def decode_course_uuid(course_uuid: str) -> int:
    return decode_public_uuid(public_id=course_uuid, expected_kind="course", secret=_get_secret())


def encode_user_uuid(user_id: int) -> str:
    return encode_public_uuid(kind="user", resource_id=user_id, secret=_get_secret())


def decode_user_uuid(user_uuid: str) -> int:
    return decode_public_uuid(public_id=user_uuid, expected_kind="user", secret=_get_secret())


def encode_forum_post_uuid(post_id: int) -> str:
    return encode_public_uuid(kind="forum_post", resource_id=post_id, secret=_get_secret())


def decode_forum_post_uuid(post_uuid: str) -> int:
    return decode_public_uuid(public_id=post_uuid, expected_kind="forum_post", secret=_get_secret())


def encode_comment_uuid(comment_id: int) -> str:
    return encode_public_uuid(kind="comment", resource_id=comment_id, secret=_get_secret())


def decode_comment_uuid(comment_uuid: str) -> int:
    return decode_public_uuid(public_id=comment_uuid, expected_kind="comment", secret=_get_secret())


def encode_notification_uuid(notification_id: int) -> str:
    return encode_public_uuid(kind="notification", resource_id=notification_id, secret=_get_secret())


def decode_notification_uuid(notification_uuid: str) -> int:
    return decode_public_uuid(public_id=notification_uuid, expected_kind="notification", secret=_get_secret())
