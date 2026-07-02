from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import CourseStatus
from app.models.modules import ModuleStatus
from app.services.ai_context_access_service import AIContextAccessService


def _course(*, educator_id: int = 5, status: CourseStatus = CourseStatus.PUBLISHED):
    return SimpleNamespace(course_id=1, educator_id=educator_id, status=status)


def _module(*, status: ModuleStatus = ModuleStatus.PUBLISHED, class_id: str | None = None):
    return SimpleNamespace(module_id=2, learning_path_id=10, status=status, visible_to_class_id=class_id)


def _enrollment(status: EnrollmentStatus = EnrollmentStatus.ACTIVE):
    return SimpleNamespace(enrollment_status=status)


def _service(
    monkeypatch,
    *,
    course=None,
    module=None,
    enrollment=None,
    unlock_error: HTTPException | None = None,
) -> AIContextAccessService:
    monkeypatch.setattr("app.services.ai_context_access_service.decode_course_uuid", lambda _value: 1)
    monkeypatch.setattr("app.services.ai_context_access_service.decode_module_uuid", lambda _value: 2)

    service = AIContextAccessService(SimpleNamespace())
    service.courses = SimpleNamespace(get_by_id=lambda _course_id: course)
    service.learning_paths = SimpleNamespace(
        get_by_course_id=lambda _course_id: SimpleNamespace(learning_path_id=10) if course is not None else None
    )
    service.modules = SimpleNamespace(get_by_id=lambda _module_id: module)
    service.enrollments = SimpleNamespace(get_by_course_and_learner=lambda **_kwargs: enrollment)

    def _ensure_module_unlocked(**_kwargs):
        if unlock_error is not None:
            raise unlock_error

    service.unlocking = SimpleNamespace(ensure_module_unlocked=_ensure_module_unlocked)
    return service


def test_learner_chat_context_requires_enrollment_and_unlocked_module(monkeypatch) -> None:
    # Tests enrolled learners can use AI only after module-level access passes.
    service = _service(
        monkeypatch,
        course=_course(),
        module=_module(),
        enrollment=_enrollment(),
    )

    service.ensure_chat_context_access(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        user_id=7,
        identity="Learner",
    )


def test_learner_chat_context_rejects_unenrolled_course(monkeypatch) -> None:
    # Tests RAG cannot expose a course simply because the caller knows its UUID.
    service = _service(
        monkeypatch,
        course=_course(),
        module=_module(),
        enrollment=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_chat_context_access(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            user_id=7,
            identity="Learner",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "COURSE_ENROLLMENT_REQUIRED"


def test_learner_chat_context_requires_explicit_module(monkeypatch) -> None:
    # Tests course-level learner RAG cannot sweep locked or future module content.
    service = _service(
        monkeypatch,
        course=_course(),
        module=_module(),
        enrollment=_enrollment(),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_chat_context_access(
            course_uuid="course-uuid",
            module_uuid=None,
            user_id=7,
            identity="Learner",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "AI_MODULE_CONTEXT_REQUIRED"


def test_learner_chat_context_preserves_module_lock(monkeypatch) -> None:
    # Tests module prerequisite locks also protect AI retrieval context.
    locked = HTTPException(
        status_code=423,
        detail={"code": "MODULE_LOCKED", "message": "Complete the prerequisite module first"},
    )
    service = _service(
        monkeypatch,
        course=_course(),
        module=_module(),
        enrollment=_enrollment(),
        unlock_error=locked,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_chat_context_access(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            user_id=7,
            identity="Learner",
        )

    assert exc_info.value.status_code == 423
    assert exc_info.value.detail["code"] == "MODULE_LOCKED"


def test_educator_chat_context_is_limited_to_owned_courses(monkeypatch) -> None:
    # Tests educators cannot use AI context for courses owned by another teacher.
    service = _service(
        monkeypatch,
        course=_course(educator_id=99, status=CourseStatus.DRAFT),
        module=_module(status=ModuleStatus.DRAFT),
        enrollment=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_chat_context_access(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            user_id=7,
            identity="Educator",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "AI_CONTEXT_FORBIDDEN"
