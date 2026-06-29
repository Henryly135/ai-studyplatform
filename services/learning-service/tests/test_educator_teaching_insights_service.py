from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.module_progress import ProgressStatus
from app.services.course_management_service import CourseManagementService


class FakeCourses:
    def __init__(self, courses):
        self.courses = list(courses)
        self.requested_educator_id = None

    def list_by_educator(self, educator_id: int):
        self.requested_educator_id = educator_id
        return self.courses


class FakeByCourse:
    def __init__(self, rows_by_course):
        self.rows_by_course = rows_by_course

    def get_by_course_id(self, course_id: int):
        return self.rows_by_course.get(course_id)

    def list_current_by_course(self, course_id: int):
        return list(self.rows_by_course.get(course_id, []))


class FakeModules:
    def __init__(self, modules_by_path):
        self.modules_by_path = modules_by_path

    def list_by_learning_path(self, learning_path_id: int):
        return list(self.modules_by_path.get(learning_path_id, []))


class FakeModuleProgress:
    def __init__(self, progress_rows):
        self.progress_rows = list(progress_rows)
        self.requested_learner_ids = []

    def list_by_module_ids(self, module_ids: list[int], *, learner_ids: list[int] | None = None):
        self.requested_learner_ids.append(list(learner_ids or []))
        module_id_set = set(module_ids)
        learner_id_set = set(learner_ids) if learner_ids is not None else None
        return [
            row
            for row in self.progress_rows
            if row.module_id in module_id_set and (learner_id_set is None or row.learner_id in learner_id_set)
        ]

    def aggregate_stats_by_module_ids(self, module_ids: list[int], *, learner_ids: list[int] | None = None):
        rows = self.list_by_module_ids(module_ids, learner_ids=learner_ids)
        result = []
        for module_id in module_ids:
            module_rows = [row for row in rows if row.module_id == module_id]
            if not module_rows:
                continue
            result.append(
                {
                    "module_id": module_id,
                    "started_count": sum(
                        1
                        for row in module_rows
                        if row.progress_status != ProgressStatus.NOT_STARTED or Decimal(row.progress_percent) > 0
                    ),
                    "completed_count": sum(
                        1 for row in module_rows if row.progress_status == ProgressStatus.COMPLETED
                    ),
                    "avg_progress_percent": sum(float(row.progress_percent) for row in module_rows) / len(module_rows),
                }
            )
        return result


class FakeQuizAttempts:
    def __init__(self, rows):
        self.rows = list(rows)
        self.requested_educator_id = None

    def aggregate_stats_by_educator(self, educator_id: int):
        self.requested_educator_id = educator_id
        return self.rows


class FakeAssessments:
    def __init__(self, assessments):
        self.assessments = list(assessments)

    def list_by_module_ids(self, module_ids: list[int]):
        module_id_set = set(module_ids)
        return [assessment for assessment in self.assessments if assessment.module_id in module_id_set]


class FakeShortAnswerSubmissions:
    def __init__(self, rows):
        self.rows = list(rows)
        self.requested_assessment_ids = None

    def aggregate_stats_by_assessment_ids(self, assessment_ids: list[int]):
        self.requested_assessment_ids = list(assessment_ids)
        assessment_id_set = set(assessment_ids)
        return [row for row in self.rows if row["assessment_id"] in assessment_id_set]


def _course(course_id=1, educator_id=7, title="Algorithms"):
    return SimpleNamespace(course_id=course_id, educator_id=educator_id, title=title)


def _module(module_id: int, title: str, sort_order: int = 1):
    return SimpleNamespace(module_id=module_id, title=title, sort_order=sort_order)


def _enrollment(learner_id: int, progress: str, completed: int, total: int, last_accessed_at=None):
    return SimpleNamespace(
        learner_id=learner_id,
        progress_percent=Decimal(progress),
        completed_module_count=completed,
        total_module_count=total,
        last_accessed_at=last_accessed_at,
    )


def _progress(module_id: int, learner_id: int, status: ProgressStatus, progress: str, completed_at=None):
    return SimpleNamespace(
        module_id=module_id,
        learner_id=learner_id,
        progress_status=status,
        progress_percent=Decimal(progress),
        completed_at=completed_at,
    )


def _service(
    *,
    courses,
    paths_by_course=None,
    modules_by_path=None,
    enrollments_by_course=None,
    progress_rows=None,
    quiz_rows=None,
    assessments=None,
    short_answer_rows=None,
):
    service = CourseManagementService.__new__(CourseManagementService)
    service.courses = FakeCourses(courses)
    service.learning_paths = FakeByCourse(paths_by_course or {})
    service.modules = FakeModules(modules_by_path or {})
    service.enrollments = FakeByCourse(enrollments_by_course or {})
    service.module_progress = FakeModuleProgress(progress_rows or [])
    service.quiz_attempts = FakeQuizAttempts(quiz_rows or [])
    service.short_answer_assessments = FakeAssessments(assessments or [])
    service.short_answer_submissions = FakeShortAnswerSubmissions(short_answer_rows or [])
    return service


def test_teaching_insights_scopes_to_current_educator_and_builds_signals(monkeypatch):
    now = datetime(2026, 6, 30, 12, 0, 0)
    old_access = datetime(2026, 6, 1, 12, 0, 0)
    monkeypatch.setattr("app.services.course_management_service.now_local", lambda: now)
    monkeypatch.setattr("app.services.course_management_service.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.services.course_management_service.encode_module_uuid", lambda value: f"module-{value}")
    monkeypatch.setattr("app.services.course_management_service.encode_user_uuid", lambda value: f"user-{value}")

    service = _service(
        courses=[_course()],
        paths_by_course={1: SimpleNamespace(learning_path_id=100, course_id=1)},
        modules_by_path={100: [_module(10, "Sorting"), _module(11, "Graphs", 2)]},
        enrollments_by_course={
            1: [
                _enrollment(101, "20.00", 0, 2, old_access),
                _enrollment(102, "100.00", 2, 2, now),
            ]
        },
        progress_rows=[
            _progress(10, 101, ProgressStatus.IN_PROGRESS, "20.00"),
            _progress(10, 102, ProgressStatus.COMPLETED, "100.00", datetime(2026, 6, 29, 10, 0, 0)),
            _progress(10, 999, ProgressStatus.COMPLETED, "100.00", datetime(2026, 6, 28, 10, 0, 0)),
        ],
        quiz_rows=[
            {
                "course_id": 1,
                "course_title": "Algorithms",
                "module_id": 10,
                "module_title": "Sorting",
                "quiz_title": "Sorting quiz",
                "total_attempts": 2,
                "unique_learners": 2,
                "avg_score_percent": 45.0,
                "pass_rate": 0.5,
                "avg_duration_seconds": 30.0,
            }
        ],
        assessments=[
            SimpleNamespace(
                short_answer_assessment_id=500,
                module_id=10,
                title="Explain sorting",
                max_score=Decimal("10.00"),
            )
        ],
        short_answer_rows=[
            {
                "assessment_id": 500,
                "submission_count": 2,
                "avg_ai_score": 5.0,
                "avg_final_score": 7.0,
                "pending_review_count": 1,
            }
        ],
    )

    result = service.get_educator_teaching_insights(current_user={"id": 7, "identity": "Educator"})

    assert service.courses.requested_educator_id == 7
    assert service.quiz_attempts.requested_educator_id == 7
    assert service.module_progress.requested_learner_ids == [[101, 102], [101, 102]]
    assert service.short_answer_submissions.requested_assessment_ids == [500]
    assert len(result.moduleBottlenecks) == 2
    sorting_bottleneck = next(item for item in result.moduleBottlenecks if item.moduleUuid == "module-10")
    assert sorting_bottleneck.completedLearnerCount == 1
    assert sorting_bottleneck.completionRate == 0.5
    graph_bottleneck = next(item for item in result.moduleBottlenecks if item.moduleUuid == "module-11")
    assert graph_bottleneck.signals == ["no_activity", "low_completion"]
    assert graph_bottleneck.completionRate == 0

    assert len(result.atRiskLearners) == 1
    risk_item = result.atRiskLearners[0]
    assert risk_item.learnerUuid == "user-101"
    assert risk_item.riskReasons == ["low_progress", "inactive_14_days", "many_incomplete_modules"]

    assert result.completionTrends[0].bucketDate.isoformat() == "2026-06-29"
    assert result.completionTrends[0].completedCount == 1
    assert len(result.completionTrends) == 1

    assert len(result.assessmentSignals) == 1
    signal_item = result.assessmentSignals[0]
    assert signal_item.shortAnswerPendingReviewCount == 1
    assert signal_item.shortAnswerAvgAiScore == 5.0
    assert signal_item.signals == [
        "low_quiz_pass_rate",
        "low_quiz_avg_score",
        "short_answer_pending_review",
    ]


def test_teaching_insights_returns_empty_arrays_without_courses():
    service = _service(courses=[])

    result = service.get_educator_teaching_insights(current_user={"id": 7, "identity": "Educator"})

    assert result.moduleBottlenecks == []
    assert result.atRiskLearners == []
    assert result.completionTrends == []
    assert result.assessmentSignals == []
    assert service.quiz_attempts.requested_educator_id is None


def test_teaching_insights_rejects_invalid_identity():
    service = _service(courses=[])

    with pytest.raises(HTTPException):
        service.get_educator_teaching_insights(current_user={"id": "7", "identity": "Educator"})
