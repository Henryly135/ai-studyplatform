from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.short_answer_assessments import ShortAnswerAssessmentStatus
from app.models.short_answer_submissions import ShortAnswerSubmissionStatus
from app.schemas.short_answer import (
    ShortAnswerAssessmentUpsertRequest,
    ShortAnswerSubmissionCreateRequest,
    ShortAnswerSubmissionReviewRequest,
)
from app.services.short_answer_service import ShortAnswerService


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.refreshed = []

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, obj) -> None:
        self.refreshed.append(obj)


class FakeAssessmentRepository:
    def __init__(self, assessment=None) -> None:
        self.assessment = assessment
        self.created = []

    def get_by_module_id(self, module_id: int):
        return self.assessment if self.assessment and self.assessment.module_id == module_id else None

    def create(self, **kwargs):
        self.assessment = SimpleNamespace(
            short_answer_assessment_id=20,
            assessment_uuid="assessment-uuid",
            created_at=datetime(2026, 6, 30, 12, 0, 0),
            updated_at=datetime(2026, 6, 30, 12, 0, 0),
            **kwargs,
        )
        self.created.append(self.assessment)
        return self.assessment

    def update(self, assessment, **kwargs):
        for key, value in kwargs.items():
            setattr(assessment, key, value)
        return assessment


class FakeSubmissionRepository:
    def __init__(self, submissions=None) -> None:
        self.submissions = list(submissions or [])
        self.created = []

    def get_by_uuid(self, submission_uuid: str):
        return next((submission for submission in self.submissions if submission.submission_uuid == submission_uuid), None)

    def get_latest_by_assessment_and_learner(self, assessment_id: int, learner_id: int):
        rows = [s for s in self.submissions if s.assessment_id == assessment_id and s.learner_id == learner_id]
        return rows[0] if rows else None

    def list_by_assessment(self, assessment_id: int):
        return [submission for submission in self.submissions if submission.assessment_id == assessment_id]

    def create(self, **kwargs):
        submission = SimpleNamespace(
            short_answer_submission_id=len(self.submissions) + 100,
            submission_uuid=f"submission-{len(self.submissions) + 1}",
            final_score=None,
            final_feedback_text=None,
            review_notes=None,
            reviewer_id=None,
            reviewed_at=None,
            created_at=datetime(2026, 6, 30, 12, 0, 0),
            updated_at=datetime(2026, 6, 30, 12, 0, 0),
            **kwargs,
        )
        self.submissions.append(submission)
        self.created.append(submission)
        return submission

    def update_review(self, submission, **kwargs):
        for key, value in kwargs.items():
            setattr(submission, key, value)
        submission.status = ShortAnswerSubmissionStatus.REVIEWED
        return submission


class FakeAIClient:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {
            "scoreSuggestion": "8.00",
            "feedbackText": "Clear response with good rubric coverage.",
            "strengths": ["Explains the main concept."],
            "improvements": ["Add one concrete example."],
            "provider": "test",
            "model": "stub",
        }
        self.calls = []

    def evaluate_submission(self, payload):
        self.calls.append(payload)
        return self.response


def _course():
    return SimpleNamespace(course_id=1, educator_id=7, title="Algorithms", status=SimpleNamespace(value="published"))


def _module():
    return SimpleNamespace(module_id=2, title="Graphs", status=SimpleNamespace(value="published"))


def _assessment(status=ShortAnswerAssessmentStatus.PUBLISHED, max_score=Decimal("10.00")):
    return SimpleNamespace(
        short_answer_assessment_id=20,
        assessment_uuid="assessment-uuid",
        module_id=2,
        title="Explain BFS",
        prompt_text="Explain how BFS explores a graph.",
        rubric_text="Mentions queue, levels, visited nodes, and traversal order.",
        max_score=max_score,
        status=status,
        created_by=7,
        updated_by=7,
        published_at=datetime(2026, 6, 30, 12, 0, 0) if status == ShortAnswerAssessmentStatus.PUBLISHED else None,
        created_at=datetime(2026, 6, 30, 12, 0, 0),
        updated_at=datetime(2026, 6, 30, 12, 0, 0),
    )


def _submission(assessment_id=20):
    return SimpleNamespace(
        short_answer_submission_id=100,
        submission_uuid="submission-uuid",
        assessment_id=assessment_id,
        learner_id=9,
        answer_text="BFS uses a queue and visits nodes level by level.",
        ai_score_suggestion=Decimal("8.00"),
        ai_feedback_text="Good start.",
        ai_strengths_json=["Mentions queue."],
        ai_improvements_json=["Add visited set."],
        ai_provider_name="test",
        ai_provider_model="stub",
        final_score=None,
        final_feedback_text=None,
        review_notes=None,
        reviewer_id=None,
        reviewed_at=None,
        status=ShortAnswerSubmissionStatus.AI_SUGGESTED,
        created_at=datetime(2026, 6, 30, 12, 0, 0),
        updated_at=datetime(2026, 6, 30, 12, 0, 0),
    )


def _service(monkeypatch, *, assessment=None, submissions=None, ai_response=None):
    session = FakeSession()
    service = ShortAnswerService(session, ai_client=FakeAIClient(ai_response))
    service.assessments = FakeAssessmentRepository(assessment)
    service.submissions = FakeSubmissionRepository(submissions)
    service._get_manageable_course = lambda **_: _course()
    service._get_course = lambda _: _course()
    service._get_course_module = lambda **_: _module()
    service._ensure_learner_can_access_module = lambda **_: None
    service._ensure_module_unlocked = lambda **_: None
    monkeypatch.setattr("app.services.short_answer_service.encode_module_uuid", lambda module_id: f"module-{module_id}")
    return service, session


def test_upsert_assessment_creates_published_record(monkeypatch) -> None:
    service, session = _service(monkeypatch)

    result = service.upsert_assessment(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        payload=ShortAnswerAssessmentUpsertRequest(
            title="Explain BFS",
            promptText="Explain how BFS explores a graph.",
            rubricText="Mentions queue, levels, visited nodes, and traversal order.",
            maxScore=Decimal("10.00"),
            status="published",
        ),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert result.status == "published"
    assert result.publishedAt is not None
    assert result.maxScore == Decimal("10.00")
    assert session.commits == 1
    assert service.assessments.created[0].created_by == 7


def test_submit_answer_saves_ai_suggestion(monkeypatch) -> None:
    assessment = _assessment()
    service, session = _service(monkeypatch, assessment=assessment)

    result = service.submit_answer(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        payload=ShortAnswerSubmissionCreateRequest(answerText="BFS uses a queue and visits nodes level by level."),
        current_user={"id": 9, "identity": "Learner"},
    )

    assert result.status == "ai_suggested"
    assert result.aiSuggestion.scoreSuggestion == Decimal("8.00")
    assert service.submissions.created[0].ai_feedback_text == "Clear response with good rubric coverage."
    assert service.ai_client.calls[0].assessmentUuid == "assessment-uuid"
    assert session.commits == 1


def test_learner_assessment_hides_private_review_notes(monkeypatch) -> None:
    reviewed_submission = _submission()
    reviewed_submission.status = ShortAnswerSubmissionStatus.REVIEWED
    reviewed_submission.final_score = Decimal("8.50")
    reviewed_submission.final_feedback_text = "Final educator feedback."
    reviewed_submission.review_notes = "Private calibration note."
    reviewed_submission.reviewer_id = 7
    reviewed_submission.reviewed_at = datetime(2026, 6, 30, 13, 0, 0)
    service, _ = _service(monkeypatch, assessment=_assessment(), submissions=[reviewed_submission])

    result = service.get_learner_assessment(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        current_user={"id": 9, "identity": "Learner"},
    )

    assert result.latestSubmission is not None
    assert result.latestSubmission.finalScore == Decimal("8.50")
    assert result.latestSubmission.finalFeedbackText == "Final educator feedback."
    assert result.latestSubmission.reviewNotes is None
    assert result.latestSubmission.reviewerId is None


def test_submit_answer_rejects_invalid_ai_score_without_partial_write(monkeypatch) -> None:
    service, session = _service(
        monkeypatch,
        assessment=_assessment(max_score=Decimal("5.00")),
        ai_response={
            "scoreSuggestion": "8.00",
            "feedbackText": "Too high.",
            "strengths": [],
            "improvements": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        service.submit_answer(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=ShortAnswerSubmissionCreateRequest(answerText="BFS uses a queue."),
            current_user={"id": 9, "identity": "Learner"},
        )

    assert exc_info.value.status_code == 502
    assert service.submissions.created == []
    assert session.commits == 0


def test_learner_cannot_access_draft_assessment(monkeypatch) -> None:
    service, session = _service(monkeypatch, assessment=_assessment(status=ShortAnswerAssessmentStatus.DRAFT))

    with pytest.raises(HTTPException) as exc_info:
        service.get_learner_assessment(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            current_user={"id": 9, "identity": "Learner"},
        )

    assert exc_info.value.status_code == 404
    assert session.commits == 0


def test_review_submission_saves_final_feedback(monkeypatch) -> None:
    service, session = _service(monkeypatch, assessment=_assessment(max_score=Decimal("10.00")), submissions=[_submission()])

    result = service.review_submission(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        submission_uuid="submission-uuid",
        payload=ShortAnswerSubmissionReviewRequest(
            finalScore=Decimal("9.00"),
            finalFeedbackText="Good explanation with clear traversal details.",
            reviewNotes="Checked against rubric.",
        ),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert result.status == "reviewed"
    assert result.finalScore == Decimal("9.00")
    assert result.finalFeedbackText == "Good explanation with clear traversal details."
    assert result.reviewNotes == "Checked against rubric."
    assert result.reviewerId == 7
    assert result.reviewedAt is not None
    assert session.commits == 1


def test_review_rejects_score_above_assessment_max(monkeypatch) -> None:
    service, session = _service(monkeypatch, assessment=_assessment(max_score=Decimal("5.00")), submissions=[_submission()])

    with pytest.raises(HTTPException):
        service.review_submission(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            submission_uuid="submission-uuid",
            payload=ShortAnswerSubmissionReviewRequest(finalScore=Decimal("7.00"), finalFeedbackText="Reviewed."),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert service.submissions.submissions[0].status == ShortAnswerSubmissionStatus.AI_SUGGESTED
    assert session.commits == 0


def test_upsert_permission_failure_short_circuits_write(monkeypatch) -> None:
    service, session = _service(monkeypatch)

    def deny_course(**_):
        raise HTTPException(status_code=403, detail="forbidden")

    service._get_manageable_course = deny_course

    with pytest.raises(HTTPException) as exc_info:
        service.upsert_assessment(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=ShortAnswerAssessmentUpsertRequest(
                title="Explain BFS",
                promptText="Explain how BFS explores a graph.",
                rubricText="Mentions queue.",
            ),
            current_user={"id": 8, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 403
    assert service.assessments.created == []
    assert session.commits == 0
