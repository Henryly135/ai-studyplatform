from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import CourseStatus
from app.services.course_space_access_service import CourseSpaceAccessService


def _course(*, educator_id: int = 5, status: CourseStatus = CourseStatus.PUBLISHED):
    return SimpleNamespace(course_id=1, educator_id=educator_id, status=status)


def _enrollment(status: EnrollmentStatus = EnrollmentStatus.ACTIVE):
    return SimpleNamespace(enrollment_status=status)


def _service(monkeypatch, *, course=None, enrollment=None) -> CourseSpaceAccessService:
    monkeypatch.setattr("app.services.course_space_access_service.decode_course_uuid", lambda _value: 1)
    service = CourseSpaceAccessService(SimpleNamespace())
    service.courses = SimpleNamespace(get_by_id=lambda _course_id: course)
    service.enrollments = SimpleNamespace(get_by_course_and_learner=lambda **_kwargs: enrollment)
    return service


def test_forum_access_allows_enrolled_learner_owner_educator_and_admin(monkeypatch) -> None:
    # Tests course forum access is scoped to enrolled learners, owner educator, and admins.
    service = _service(monkeypatch, course=_course(), enrollment=_enrollment())

    service.ensure_forum_access(course_uuid="course-uuid", user_id=7, identity="Learner")
    service.ensure_forum_access(course_uuid="course-uuid", user_id=5, identity="Educator")
    service.ensure_forum_access(course_uuid="course-uuid", user_id=99, identity="Admin")


def test_forum_access_rejects_unenrolled_learners(monkeypatch) -> None:
    # Tests knowing a course UUID is not enough to read or write the course forum.
    service = _service(monkeypatch, course=_course(), enrollment=None)

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_forum_access(course_uuid="course-uuid", user_id=7, identity="Learner")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "COURSE_ENROLLMENT_REQUIRED"


def test_forum_access_rejects_non_owner_educator(monkeypatch) -> None:
    # Tests educators cannot moderate or read forums for courses they do not own.
    service = _service(monkeypatch, course=_course(educator_id=5), enrollment=None)

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_forum_access(course_uuid="course-uuid", user_id=6, identity="Educator")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "COURSE_FORUM_FORBIDDEN"


def test_forum_access_rejects_draft_course_for_learner(monkeypatch) -> None:
    # Tests learners cannot enter forums for unpublished courses.
    service = _service(
        monkeypatch,
        course=_course(status=CourseStatus.DRAFT),
        enrollment=_enrollment(),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_forum_access(course_uuid="course-uuid", user_id=7, identity="Learner")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "COURSE_NOT_AVAILABLE"
