from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import course_enrollments as course_enrollments_api
from app.models.course_enrollments import EnrollmentStatus
from app.models.module_progress import ProgressStatus
from app.schemas.learner_progress import LearnerProgressOverviewResponse, LearnerProgressQuizSummary
from app.services import learner_progress_service as progress_module
from app.services.learner_progress_service import LearnerProgressService


NOW = datetime(2026, 7, 2, 12, 0, 0)


def test_progress_overview_includes_quiz_scores_and_recent_activity(monkeypatch) -> None:
    # Tests learner Progress has module, quiz, and recent activity evidence in one aggregate response.
    monkeypatch.setattr(progress_module, "encode_course_uuid", lambda course_id: f"course-{course_id}")
    monkeypatch.setattr(progress_module, "encode_module_uuid", lambda module_id: f"module-{module_id}")

    enrollment = SimpleNamespace(
        enrollment_id=1,
        course_id=1,
        learner_id=7,
        enrollment_status=EnrollmentStatus.ACTIVE,
        progress_percent=Decimal("50.00"),
        completed_module_count=1,
        total_module_count=2,
        last_accessed_at=NOW,
        enrolled_at=NOW - timedelta(days=10),
        completed_at=None,
    )
    course = SimpleNamespace(course_id=1, title="Physics", category="Science")
    completed_module = SimpleNamespace(module_id=10, title="Forces")
    next_module = SimpleNamespace(module_id=11, title="Energy")
    completed_progress = SimpleNamespace(
        module_id=10,
        progress_status=ProgressStatus.COMPLETED,
        completed_at=NOW - timedelta(hours=2),
        last_accessed_at=NOW - timedelta(hours=2),
    )
    active_progress = SimpleNamespace(
        module_id=11,
        progress_status=ProgressStatus.IN_PROGRESS,
        completed_at=None,
        last_accessed_at=NOW - timedelta(hours=1),
    )
    quiz = SimpleNamespace(quiz_id=100, module_id=10, title="Forces Check")
    next_quiz = SimpleNamespace(quiz_id=101, module_id=11, title="Energy Check")
    first_attempt = SimpleNamespace(
        quiz_attempt_id=1000,
        quiz_id=100,
        attempt_number=1,
        score_percent=Decimal("60.00"),
        is_passed=False,
        submitted_at=NOW - timedelta(hours=3),
    )
    latest_attempt = SimpleNamespace(
        quiz_attempt_id=1001,
        quiz_id=100,
        attempt_number=2,
        score_percent=Decimal("100.00"),
        is_passed=True,
        submitted_at=NOW - timedelta(minutes=20),
    )

    service = LearnerProgressService(SimpleNamespace())
    service.unlocking = SimpleNamespace(is_module_unlocked=lambda *, module_id, learner_id: module_id == 11)
    service._load_enrolled_course_rows = lambda learner_id: [(enrollment, course)]
    service._load_modules_by_course = lambda course_ids: {1: [completed_module, next_module]}
    service._load_progress_by_module = lambda *, learner_id, module_ids: {
        10: completed_progress,
        11: active_progress,
    }
    service._load_quizzes_by_module = lambda module_ids: {10: quiz, 11: next_quiz}
    service._load_attempts_by_quiz = lambda *, learner_id, quiz_ids: {100: [latest_attempt, first_attempt]}

    response = service.get_overview(current_user={"id": 7, "identity": "Learner"})

    assert response.totalCourses == 1
    assert response.completedModules == 1
    assert response.quiz.totalQuizzes == 2
    assert response.quiz.attemptedQuizzes == 1
    assert response.quiz.passedQuizzes == 1
    assert response.quiz.totalAttempts == 2
    assert response.quiz.averageBestScorePercent == 100
    assert response.quiz.latestScorePercent == 100
    assert response.courses[0].nextModule is not None
    assert response.courses[0].nextModule.moduleUuid == "module-11"
    assert response.recentActivity[0].activityType == "quiz_submitted"
    assert response.recentActivity[0].scorePercent == 100
    assert {item.activityType for item in response.recentActivity} >= {
        "module_completed",
        "module_accessed",
        "quiz_submitted",
    }


def test_progress_overview_rejects_non_learners() -> None:
    service = LearnerProgressService(SimpleNamespace())

    with pytest.raises(HTTPException) as exc_info:
        service.get_overview(current_user={"id": 2, "identity": "Educator"})

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "LEARNER_ONLY"


def test_progress_overview_api_uses_current_user(monkeypatch) -> None:
    # Tests the API handler delegates to the aggregate service with the authenticated identity.
    calls = []

    class FakeProgressService:
        def __init__(self, session) -> None:
            self.session = session

        def get_overview(self, *, current_user):
            calls.append(current_user)
            return LearnerProgressOverviewResponse(
                totalCourses=0,
                totalModules=0,
                completedModules=0,
                averageProgressPercent=0,
                quiz=LearnerProgressQuizSummary(
                    totalQuizzes=0,
                    attemptedQuizzes=0,
                    passedQuizzes=0,
                    totalAttempts=0,
                ),
                courses=[],
                recentActivity=[],
            )

    monkeypatch.setattr(course_enrollments_api, "LearnerProgressService", FakeProgressService)

    response = course_enrollments_api.get_my_progress_overview(
        current_user={"id": 7, "identity": "Learner"},
        session=object(),
    )

    assert calls == [{"id": 7, "identity": "Learner"}]
    assert response.totalCourses == 0
