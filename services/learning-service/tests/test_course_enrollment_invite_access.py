from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import CourseStatus
from app.api import course_invites as course_invites_api
from app.core.public_url import PublicFrontendUrlNotConfiguredError
from app.services.course_enrollment_service import (
    CourseEnrollmentService,
    CourseNotAvailableForEnrollmentError,
)
from app.services import course_invite_service as course_invite_module
from app.services.course_invite_service import CourseInviteService


NOW = datetime(2026, 7, 2, 12, 0, 0)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = []

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item) -> None:
        self.refreshed.append(item)


class FakeRequest:
    def __init__(self, headers=None, scheme: str = "http") -> None:
        self.headers = headers or {}
        self.url = SimpleNamespace(scheme=scheme)


class FakeEnrollments:
    def __init__(self) -> None:
        self.created = []
        self.existing = None

    def get_by_course_and_learner(self, *, course_id: int, learner_id: int):
        return self.existing

    def create(self, **kwargs):
        enrollment = SimpleNamespace(
            enrollment_id=len(self.created) + 1,
            enrolled_at=NOW,
            last_accessed_at=None,
            completed_at=None,
            enrollment_status=EnrollmentStatus.ACTIVE,
            **kwargs,
        )
        self.created.append(enrollment)
        return enrollment

    def update_progress(self, enrollment, **kwargs):
        for key, value in kwargs.items():
            setattr(enrollment, key, value)
        return enrollment

    def update_status(self, enrollment, **kwargs):
        for key, value in kwargs.items():
            setattr(enrollment, key, value)
        return enrollment


def _course(*, status: CourseStatus = CourseStatus.PUBLISHED, is_public: bool = True):
    return SimpleNamespace(
        course_id=1,
        title="Course",
        educator_id=5,
        status=status,
        is_public=is_public,
    )


def _wire_common_service(monkeypatch, service, *, course):
    monkeypatch.setattr("app.services.course_enrollment_service.decode_course_uuid", lambda _value: 1)
    monkeypatch.setattr("app.services.course_enrollment_service.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.services.course_enrollment_service.encode_user_uuid", lambda value: f"user-{value}")
    service.courses = SimpleNamespace(get_by_id=lambda _course_id: course)
    service.enrollments = FakeEnrollments()
    service.aggregates = SimpleNamespace(build_initial_aggregate=lambda **_kwargs: (2, "0.00"))
    service.audit_logs = SimpleNamespace(create=lambda **_kwargs: None)
    profile_calls = []
    service.profile_triggers = SimpleNamespace(
        initialize_currently_unlocked_for_enrollment=lambda **kwargs: profile_calls.append(kwargs)
    )
    return profile_calls


def test_public_enrollment_rejects_unpublished_or_private_courses(monkeypatch) -> None:
    # Tests public enrolment cannot bypass course publication/visibility state.
    for course in [
        _course(status=CourseStatus.DRAFT, is_public=True),
        _course(status=CourseStatus.PUBLISHED, is_public=False),
    ]:
        service = CourseEnrollmentService(FakeSession())
        profile_calls = _wire_common_service(monkeypatch, service, course=course)

        with pytest.raises(CourseNotAvailableForEnrollmentError):
            service.enrol_course(
                course_uuid="course-uuid",
                current_user={"id": 7, "identity": "Learner"},
            )

        assert service.enrollments.created == []
        assert profile_calls == []


def test_public_enrollment_allows_published_public_course_and_initializes_profile(monkeypatch) -> None:
    # Tests normal enrolment still works for published public courses.
    session = FakeSession()
    service = CourseEnrollmentService(session)
    profile_calls = _wire_common_service(monkeypatch, service, course=_course())

    response = service.enrol_course(
        course_uuid="course-uuid",
        current_user={"id": 7, "identity": "Learner"},
    )

    assert response.courseUuid == "course-1"
    assert session.committed is True
    assert profile_calls == [{"course_id": 1, "learner_id": 7}]


def _wire_invite_service(monkeypatch, service, *, course):
    monkeypatch.setattr("app.services.course_invite_service.encode_course_uuid", lambda value: f"course-{value}")
    service.courses = SimpleNamespace(get_by_id=lambda _course_id: course)
    service.enrollments = FakeEnrollments()
    service.aggregates = SimpleNamespace(build_initial_aggregate=lambda **_kwargs: (2, "0.00"))
    service.audit_logs = SimpleNamespace(create=lambda **_kwargs: None)
    invite = SimpleNamespace(invite_uuid="invite-token", course_id=1)
    service.invite_tokens = SimpleNamespace(get_valid_by_uuid=lambda _token: invite)
    profile_calls = []
    service.profile_triggers = SimpleNamespace(
        initialize_currently_unlocked_for_enrollment=lambda **kwargs: profile_calls.append(kwargs)
    )
    return profile_calls


def test_invite_validation_and_enrolment_reject_unpublished_courses(monkeypatch) -> None:
    # Tests invite tokens do not expose or enroll learners into draft courses.
    service = CourseInviteService(FakeSession())
    _wire_invite_service(monkeypatch, service, course=_course(status=CourseStatus.DRAFT))

    with pytest.raises(HTTPException) as validate_error:
        service.validate_invite_token(token="invite-token")
    with pytest.raises(HTTPException) as enrol_error:
        service.enrol_via_invite(
            token="invite-token",
            current_user={"id": 7, "identity": "Learner"},
        )

    assert validate_error.value.status_code == 404
    assert enrol_error.value.status_code == 404


def test_invite_enrolment_initializes_unlocked_module_profiles(monkeypatch) -> None:
    # Tests invite enrolment follows the same profile initialization path as public enrolment.
    session = FakeSession()
    service = CourseInviteService(session)
    profile_calls = _wire_invite_service(monkeypatch, service, course=_course(is_public=False))

    response = service.enrol_via_invite(
        token="invite-token",
        current_user={"id": 7, "identity": "Learner"},
    )

    assert response["courseUuid"] == "course-1"
    assert session.committed is True
    assert profile_calls == [{"course_id": 1, "learner_id": 7}]


def test_course_invite_url_uses_configured_frontend_base(monkeypatch) -> None:
    # Tests generated course invite links use configured public frontend URLs before local fallback.
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "https://app.example/")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example/api")

    assert course_invite_module._build_course_invite_url("token") == "https://app.example/courses/join?token=token"

    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)

    assert course_invite_module._build_course_invite_url("token") == "https://api.example/courses/join?token=token"


def test_course_invite_url_fails_closed_in_production_without_config(monkeypatch) -> None:
    # Tests production never creates learner-facing course invite links from localhost fallback.
    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(PublicFrontendUrlNotConfiguredError):
        course_invite_module._build_course_invite_url("token")


def test_course_invite_api_prefers_configured_frontend_over_spoofed_origin(monkeypatch) -> None:
    # Tests course invite APIs pass a trusted configured frontend URL into the service.
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "https://app.example")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    calls = []

    class FakeCourseInviteService:
        def __init__(self, session):
            pass

        def generate_invite_link(self, **kwargs):
            calls.append(("generate", kwargs))
            return {"inviteUrl": "ok"}

        def list_invite_links(self, **kwargs):
            calls.append(("list", kwargs))
            return []

    monkeypatch.setattr(course_invites_api, "CourseInviteService", FakeCourseInviteService)
    request = FakeRequest(headers={"origin": "https://evil.example", "x-public-frontend-url": "https://evil.example"})

    assert course_invites_api.generate_course_invite_link("course-uuid", request, {"id": 5}, object()) == {"inviteUrl": "ok"}
    assert course_invites_api.list_course_invite_links("course-uuid", request, {"id": 5}, object()) == []
    assert [call[0] for call in calls] == ["generate", "list"]
    assert all(call[1]["public_frontend_base_url"] == "https://app.example" for call in calls)


def test_course_invite_api_requires_public_frontend_url_in_production(monkeypatch) -> None:
    # Tests production does not generate or list invite links using caller-supplied public URL headers.
    monkeypatch.delenv("PUBLIC_FRONTEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    calls = []

    class FakeCourseInviteService:
        def __init__(self, session):
            pass

        def generate_invite_link(self, **kwargs):
            calls.append(("generate", kwargs))
            return {"inviteUrl": "ok"}

        def list_invite_links(self, **kwargs):
            calls.append(("list", kwargs))
            return []

    monkeypatch.setattr(course_invites_api, "CourseInviteService", FakeCourseInviteService)
    request = FakeRequest(headers={"origin": "https://evil.example", "x-public-frontend-url": "https://evil.example"})

    with pytest.raises(HTTPException) as generate_exc:
        course_invites_api.generate_course_invite_link("course-uuid", request, {"id": 5}, object())
    with pytest.raises(HTTPException) as list_exc:
        course_invites_api.list_course_invite_links("course-uuid", request, {"id": 5}, object())

    assert generate_exc.value.status_code == 500
    assert generate_exc.value.detail == "Course invite link generation is temporarily unavailable."
    assert "frontend" not in generate_exc.value.detail.lower()
    assert "evil.example" not in generate_exc.value.detail
    assert list_exc.value.status_code == 500
    assert list_exc.value.detail == "Course invite link generation is temporarily unavailable."
    assert "frontend" not in list_exc.value.detail.lower()
    assert "evil.example" not in list_exc.value.detail
    assert calls == []
