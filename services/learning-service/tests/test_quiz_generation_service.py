from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.uuid_codec import encode_quiz_question_uuid
from app.models.modules import ModuleStatus
from app.models.quizzes import QuizStatus
from app.schemas.quiz import QuizQuestionWriteRequest
from app.services.quiz_service import GENERATED_ATTEMPT_QUIZ_SORT_ORDER_BASE, QuizService


class FakeSession:
    def commit(self) -> None:
        pass

    def refresh(self, _obj) -> None:
        pass


class FakeQuestions:
    def __init__(self, initial_questions=None) -> None:
        self.rows = list(initial_questions or [])
        self.next_id = max((row.quiz_question_id for row in self.rows), default=100) + 1

    def list_by_quiz(self, quiz_id: int):
        return [row for row in self.rows if row.quiz_id == quiz_id]

    def list_active_by_quiz(self, quiz_id: int):
        return [
            row
            for row in self.rows
            if row.quiz_id == quiz_id and row.is_active and row.sort_order < 10_000_000
        ]

    def list_by_ids(self, question_ids: list[int]):
        requested = set(question_ids)
        return [row for row in self.rows if row.quiz_question_id in requested]

    def create(self, *, quiz_id: int, question_text: str, explanation_text: str | None, sort_order: int, is_active: bool):
        row = SimpleNamespace(
            quiz_question_id=self.next_id,
            quiz_id=quiz_id,
            question_text=question_text,
            explanation_text=explanation_text,
            sort_order=sort_order,
            is_active=is_active,
        )
        self.next_id += 1
        self.rows.append(row)
        return row


class FakeOptions:
    def __init__(self) -> None:
        self.rows_by_question: dict[int, list[SimpleNamespace]] = {}
        self.next_id = 500

    def delete_by_question(self, question_id: int) -> None:
        self.rows_by_question[question_id] = []

    def create(self, *, quiz_question_id: int, option_label: str | None, option_text: str, sort_order: int, is_correct: bool):
        row = SimpleNamespace(
            quiz_question_option_id=self.next_id,
            option_label=option_label,
            option_text=option_text,
            sort_order=sort_order,
            is_correct=is_correct,
        )
        self.next_id += 1
        self.rows_by_question.setdefault(quiz_question_id, []).append(row)
        return row

    def list_by_question(self, question_id: int):
        return list(self.rows_by_question.get(question_id, []))


class FakeAttemptSessions:
    def __init__(self) -> None:
        self.created = None

    def issue_attempt_number(self, **_kwargs) -> int:
        return 1

    def create_session(self, attempt_session) -> None:
        self.created = attempt_session


def _question_payload(text: str) -> QuizQuestionWriteRequest:
    return QuizQuestionWriteRequest(
        questionText=text,
        explanationText="Because.",
        sortOrder=1,
        isActive=True,
        options=[
            {"optionLabel": "A", "optionText": "Correct", "sortOrder": 1, "isCorrect": True},
            {"optionLabel": "B", "optionText": "Wrong", "sortOrder": 2, "isCorrect": False},
        ],
    )


def _service_for_generated_quiz(*, initial_questions=None):
    service = QuizService(FakeSession())
    course = SimpleNamespace(course_id=1)
    module = SimpleNamespace(module_id=2, status=ModuleStatus.PUBLISHED)
    quiz = SimpleNamespace(
        quiz_id=3,
        module_id=2,
        status=QuizStatus.PUBLISHED,
        published_at="published",
        question_count_per_attempt=1,
        time_limit_seconds=None,
        shuffle_options=False,
    )
    service._get_course = lambda _course_uuid: course
    service._get_course_module = lambda **_kwargs: module
    service._get_module_quiz = lambda _module_id: quiz
    service._ensure_learner_can_access_module = lambda **_kwargs: None
    service._ensure_module_unlocked = lambda **_kwargs: None
    service._ensure_quiz_publishable = lambda _quiz: None
    service.courses = SimpleNamespace(touch=lambda _course: None)
    service.quizzes = SimpleNamespace(
        update=lambda quiz, **kwargs: [setattr(quiz, key, value) for key, value in kwargs.items()]
    )
    service.questions = FakeQuestions(initial_questions)
    service.options = FakeOptions()
    service.attempts = SimpleNamespace(get_max_attempt_number=lambda **_kwargs: 0)
    service.attempt_sessions = FakeAttemptSessions()
    return service


def test_batch_create_generated_questions_stores_hidden_inactive_questions() -> None:
    official_question = SimpleNamespace(
        quiz_question_id=10,
        quiz_id=3,
        question_text="Official",
        explanation_text=None,
        sort_order=1,
        is_active=True,
    )
    service = _service_for_generated_quiz(initial_questions=[official_question])

    result = service.batch_create_generated_questions(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        purpose="attempt",
        questions=[_question_payload("Generated 1"), _question_payload("Generated 2")],
    )

    created_rows = [row for row in service.questions.rows if row.quiz_question_id != official_question.quiz_question_id]
    assert len(result.createdQuestions) == 2
    assert len(created_rows) == 2
    assert all(row.is_active is False for row in created_rows)
    assert all(row.sort_order > GENERATED_ATTEMPT_QUIZ_SORT_ORDER_BASE for row in created_rows)
    assert service.questions.list_active_by_quiz(3) == [official_question]


def test_authoring_generated_questions_remain_visible_and_return_quiz_to_draft() -> None:
    official_question = SimpleNamespace(
        quiz_question_id=10,
        quiz_id=3,
        question_text="Official",
        explanation_text=None,
        sort_order=1,
        is_active=True,
    )
    service = _service_for_generated_quiz(initial_questions=[official_question])
    quiz = service._get_module_quiz(2)

    service.batch_create_generated_questions(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        questions=[_question_payload("Teacher draft")],
    )

    created_row = next(row for row in service.questions.rows if row.quiz_question_id != official_question.quiz_question_id)
    assert created_row.is_active is True
    assert created_row.sort_order == 2
    assert quiz.status == QuizStatus.DRAFT
    assert quiz.published_at is None


def test_authoring_generation_access_allows_owner_and_admin() -> None:
    # Tests AI authoring generation uses the same owner/admin boundary as quiz management.
    service = QuizService(FakeSession())
    checked_modules = []
    service._get_course = lambda _course_uuid: SimpleNamespace(course_id=1, educator_id=7)
    service._get_course_module = lambda **kwargs: checked_modules.append(kwargs) or SimpleNamespace(module_id=2)

    service.ensure_authoring_quiz_access(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        actor_id=7,
        actor_identity="Educator",
    )
    service.ensure_authoring_quiz_access(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        actor_id=99,
        actor_identity="Admin",
    )

    assert checked_modules == [
        {"course_id": 1, "module_uuid": "module-uuid"},
        {"course_id": 1, "module_uuid": "module-uuid"},
    ]


def test_authoring_generation_access_rejects_non_owner_educator() -> None:
    # Tests educators cannot generate authoring quiz drafts for courses they do not own.
    service = QuizService(FakeSession())
    service._get_course = lambda _course_uuid: SimpleNamespace(course_id=1, educator_id=7)
    service._get_course_module = lambda **_kwargs: SimpleNamespace(module_id=2)

    with pytest.raises(HTTPException) as error:
        service.ensure_authoring_quiz_access(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            actor_id=8,
            actor_identity="Educator",
        )

    assert error.value.status_code == 403


def test_generated_attempt_uses_hidden_questions_and_rejects_official_active_questions() -> None:
    official_question = SimpleNamespace(
        quiz_question_id=10,
        quiz_id=3,
        question_text="Official",
        explanation_text=None,
        sort_order=1,
        is_active=True,
    )
    generated_question = SimpleNamespace(
        quiz_question_id=20,
        quiz_id=3,
        question_text="Generated",
        explanation_text=None,
        sort_order=GENERATED_ATTEMPT_QUIZ_SORT_ORDER_BASE + 1,
        is_active=False,
    )
    service = _service_for_generated_quiz(initial_questions=[official_question, generated_question])
    service.options.rows_by_question[generated_question.quiz_question_id] = [
        SimpleNamespace(quiz_question_option_id=501, option_label="A", option_text="Correct", sort_order=1, is_correct=True),
        SimpleNamespace(quiz_question_option_id=502, option_label="B", option_text="Wrong", sort_order=2, is_correct=False),
    ]

    with pytest.raises(HTTPException) as error:
        service.start_generated_attempt_internal(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            learner_id=7,
            question_uuids=[encode_quiz_question_uuid(official_question.quiz_question_id)],
        )
    assert error.value.status_code == 404

    response = service.start_generated_attempt_internal(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        learner_id=7,
        question_uuids=[encode_quiz_question_uuid(generated_question.quiz_question_id)],
    )

    assert response.questionCount == 1
    assert response.questions[0].questionId == generated_question.quiz_question_id
    assert service.attempt_sessions.created is not None
