from platform_common.ids.codec import decode_public_uuid, encode_public_uuid
from platform_common.ids.secret import get_public_id_secret

from app.core.config import settings


def _get_secret() -> str:
    return get_public_id_secret(settings.public_id_secret)


def encode_course_uuid(course_id: int) -> str:
    return encode_public_uuid(kind="course", resource_id=course_id, secret=_get_secret())


def decode_course_uuid(course_uuid: str) -> int:
    return decode_public_uuid(public_id=course_uuid, expected_kind="course", secret=_get_secret())


def encode_module_uuid(module_id: int) -> str:
    return encode_public_uuid(kind="module", resource_id=module_id, secret=_get_secret())


def decode_module_uuid(module_uuid: str) -> int:
    return decode_public_uuid(public_id=module_uuid, expected_kind="module", secret=_get_secret())


def encode_material_uuid(material_id: int) -> str:
    return encode_public_uuid(kind="material", resource_id=material_id, secret=_get_secret())


def decode_material_uuid(material_uuid: str) -> int:
    return decode_public_uuid(public_id=material_uuid, expected_kind="material", secret=_get_secret())


def encode_quiz_uuid(quiz_id: int) -> str:
    return encode_public_uuid(kind="quiz", resource_id=quiz_id, secret=_get_secret())


def decode_quiz_uuid(quiz_uuid: str) -> int:
    return decode_public_uuid(public_id=quiz_uuid, expected_kind="quiz", secret=_get_secret())


def encode_quiz_question_uuid(question_id: int) -> str:
    return encode_public_uuid(kind="quiz_question", resource_id=question_id, secret=_get_secret())


def decode_quiz_question_uuid(question_uuid: str) -> int:
    return decode_public_uuid(public_id=question_uuid, expected_kind="quiz_question", secret=_get_secret())


def encode_quiz_option_uuid(option_id: int) -> str:
    return encode_public_uuid(kind="quiz_option", resource_id=option_id, secret=_get_secret())


def decode_quiz_option_uuid(option_uuid: str) -> int:
    return decode_public_uuid(public_id=option_uuid, expected_kind="quiz_option", secret=_get_secret())


def encode_quiz_attempt_uuid(attempt_id: int) -> str:
    return encode_public_uuid(kind="quiz_attempt", resource_id=attempt_id, secret=_get_secret())


def decode_quiz_attempt_uuid(attempt_uuid: str) -> int:
    return decode_public_uuid(public_id=attempt_uuid, expected_kind="quiz_attempt", secret=_get_secret())


def encode_user_uuid(user_id: int) -> str:
    return encode_public_uuid(kind="user", resource_id=user_id, secret=_get_secret())


def decode_user_uuid(user_uuid: str) -> int:
    return decode_public_uuid(public_id=user_uuid, expected_kind="user", secret=_get_secret())


def encode_content_draft_uuid(content_draft_id: int) -> str:
    return encode_public_uuid(kind="content_draft", resource_id=content_draft_id, secret=_get_secret())


def decode_content_draft_uuid(content_draft_uuid: str) -> int:
    return decode_public_uuid(public_id=content_draft_uuid, expected_kind="content_draft", secret=_get_secret())
