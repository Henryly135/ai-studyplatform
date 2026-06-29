from __future__ import annotations

from datetime import datetime
import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import quiz as quiz_api
from app.models.quizzes import QuizStatus
from app.schemas.quiz import EducatorQuizDraftAcceptRequest, EducatorQuizDraftGenerateRequest
from app.services.quiz_service import QuizService
from platform_common.permissions.codes import MODULE_UPDATE


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, obj) -> None:
        self.refreshed.append(obj)


class FakeQuizRepository:
    def __init__(self, quiz) -> None:
        self.quiz = quiz

    def get_by_module_id(self, module_id: int):
        return self.quiz if self.quiz and self.quiz.module_id == module_id else None

    def update(self, quiz, **kwargs):
        for key, value in kwargs.items():
            setattr(quiz, key, value)
        return quiz

    def create(self, **kwargs):
        self.quiz = SimpleNamespace(
            quiz_id=100,
            passing_rule=SimpleNamespace(value="all_questions_correct"),
            created_at=datetime(2026, 6, 30, 12, 0, 0),
            updated_at=datetime(2026, 6, 30, 12, 0, 0),
            **kwargs,
        )
        return self.quiz


class FakeQuestionRepository:
    def __init__(self, existing_questions) -> None:
        self.questions = list(existing_questions)
        self.created = []
        self.next_id = 200

    def list_by_quiz(self, quiz_id: int):
        return [question for question in self.questions if question.quiz_id == quiz_id]

    def count_by_quiz(self, quiz_id: int, *, active_only: bool = False) -> int:
        questions = self.list_by_quiz(quiz_id)
        if active_only:
            questions = [question for question in questions if question.is_active]
        return len([question for question in questions if question.sort_order < 10_000_000])

    def create(self, **kwargs):
        question = SimpleNamespace(quiz_question_id=self.next_id, **kwargs)
        self.next_id += 1
        self.questions.append(question)
        self.created.append(question)
        return question

    def update(self, question, **kwargs):
        for key, value in kwargs.items():
            setattr(question, key, value)
        return question


class FakeOptionRepository:
    def __init__(self) -> None:
        self.created = []

    def create(self, **kwargs):
        option = SimpleNamespace(quiz_question_option_id=len(self.created) + 1, **kwargs)
        self.created.append(option)
        return option

    def list_by_question(self, question_id: int):
        return [option for option in self.created if option.quiz_question_id == question_id]

    def delete_by_question(self, question_id: int):
        self.created = [option for option in self.created if option.quiz_question_id != question_id]


class FakeAIClient:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {"candidateSet": _candidate_set(question_count=2)}
        self.calls = []

    def generate_draft(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _course():
    return SimpleNamespace(course_id=1, educator_id=7, title="Algorithms")


def _module():
    return SimpleNamespace(module_id=2, title="Graphs")


def _quiz():
    return SimpleNamespace(
        quiz_id=3,
        module_id=2,
        title="Old Quiz",
        description="Old description",
        status=QuizStatus.PUBLISHED,
        time_limit_seconds=600,
        question_count_per_attempt=1,
        shuffle_questions=True,
        shuffle_options=False,
        published_at=datetime(2026, 6, 1, 12, 0, 0),
        passing_rule=SimpleNamespace(value="all_questions_correct"),
        created_at=datetime(2026, 6, 1, 12, 0, 0),
        updated_at=datetime(2026, 6, 1, 12, 0, 0),
    )


def _question(question_id: int = 10, *, sort_order: int = 1, active: bool = True):
    return SimpleNamespace(
        quiz_question_id=question_id,
        quiz_id=3,
        question_text="Old question",
        explanation_text=None,
        source_grounding=None,
        sort_order=sort_order,
        is_active=active,
    )


def _candidate_set(*, question_count: int = 2, questions: list[dict] | None = None) -> dict:
    return {
        "questionCount": question_count,
        "questions": questions
        if questions is not None
        else [
            {
                "questionText": "What does BFS use?",
                "explanationText": "BFS uses a queue.",
                "sourceGrounding": "Graphs notes, BFS section.",
                "sortOrder": 99,
                "isActive": True,
                "options": [
                    {"optionLabel": "A", "optionText": "Queue", "sortOrder": 5, "isCorrect": True},
                    {"optionLabel": "B", "optionText": "Stack", "sortOrder": 6, "isCorrect": False},
                ],
            },
            {
                "questionText": "What can DFS use?",
                "explanationText": "DFS can use recursion.",
                "sourceGrounding": "Graphs notes, DFS section.",
                "sortOrder": 100,
                "isActive": True,
                "options": [
                    {"optionLabel": "A", "optionText": "Recursion", "sortOrder": 1, "isCorrect": True},
                    {"optionLabel": "B", "optionText": "A FIFO queue only", "sortOrder": 2, "isCorrect": False},
                ],
            },
        ],
    }


def _service(*, quiz=None, existing_questions=None, ai_response=None):
    session = FakeSession()
    service = QuizService(session)
    service.quizzes = FakeQuizRepository(quiz)
    service.questions = FakeQuestionRepository(existing_questions or [])
    service.options = FakeOptionRepository()
    service.educator_quiz_draft_ai = FakeAIClient(ai_response)
    service._get_manageable_course = lambda **_: _course()
    service._get_course_module = lambda **_: _module()
    service.courses.touch = lambda _: None
    service._to_quiz_authoring_response = lambda **kwargs: kwargs["quiz"]
    return service, session


def test_preview_educator_ai_draft_returns_source_grounding_without_writing() -> None:
    quiz = _quiz()
    old_question = _question()
    service, session = _service(quiz=quiz, existing_questions=[old_question])

    result = service.preview_educator_ai_draft(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        payload=EducatorQuizDraftGenerateRequest(
            title="Generated Graph Quiz",
            questionCount=2,
            learningObjectives=["Understand traversal"],
        ),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert result.title == "Generated Graph Quiz"
    assert result.candidateSet.questionCount == 2
    assert result.candidateSet.questions[0].sourceGrounding == "Graphs notes, BFS section."
    assert old_question.is_active is True
    assert service.questions.created == []
    assert session.commits == 0
    assert service.educator_quiz_draft_ai.calls[0]["available_question_count"] == 1


def test_accept_educator_ai_draft_replaces_questions_and_keeps_draft() -> None:
    quiz = _quiz()
    old_question = _question()
    service, session = _service(quiz=quiz, existing_questions=[old_question])

    result = service.accept_educator_ai_draft(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        payload=EducatorQuizDraftAcceptRequest(
            title="Generated Graph Quiz",
            replaceExistingQuestions=True,
            timeLimitSeconds=900,
            shuffleQuestions=False,
            shuffleOptions=True,
            candidateSet=_candidate_set(),
        ),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert result is quiz
    assert quiz.title == "Generated Graph Quiz"
    assert quiz.status == QuizStatus.DRAFT
    assert quiz.published_at is None
    assert quiz.question_count_per_attempt == 2
    assert quiz.time_limit_seconds == 900
    assert quiz.shuffle_questions is False
    assert quiz.shuffle_options is True
    assert old_question.is_active is False
    assert old_question.sort_order >= 10_000_000
    assert [question.sort_order for question in service.questions.created] == [1, 2]
    assert service.questions.created[0].source_grounding == "Graphs notes, BFS section."
    assert len(service.options.created) == 4
    assert session.commits == 1


def test_accept_educator_ai_draft_appends_questions() -> None:
    quiz = _quiz()
    old_question = _question(sort_order=1)
    service, session = _service(quiz=quiz, existing_questions=[old_question])
    candidate_set = _candidate_set(question_count=1, questions=[_candidate_set()["questions"][0]])

    service.accept_educator_ai_draft(
        course_uuid="course-uuid",
        module_uuid="module-uuid",
        payload=EducatorQuizDraftAcceptRequest(
            title=None,
            replaceExistingQuestions=False,
            candidateSet=candidate_set,
        ),
        current_user={"id": 7, "identity": "Educator"},
    )

    assert quiz.title == "Old Quiz"
    assert old_question.is_active is True
    assert [question.sort_order for question in service.questions.created] == [2]
    assert session.commits == 1


def test_preview_rejects_ai_count_mismatch_without_writing() -> None:
    quiz = _quiz()
    old_question = _question()
    service, session = _service(
        quiz=quiz,
        existing_questions=[old_question],
        ai_response={"candidateSet": _candidate_set(question_count=1, questions=[_candidate_set()["questions"][0]])},
    )

    with pytest.raises(HTTPException) as exc_info:
        service.preview_educator_ai_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=EducatorQuizDraftGenerateRequest(questionCount=2),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 502
    assert service.questions.created == []
    assert old_question.is_active is True
    assert session.commits == 0


@pytest.mark.parametrize(
    "candidate_set",
    [
        _candidate_set(question_count=1, questions=[{**_candidate_set()["questions"][0], "options": []}]),
        _candidate_set(question_count=1, questions=[{**_candidate_set()["questions"][0], "options": ["bad"]}]),
        _candidate_set(question_count=1, questions=[{key: value for key, value in _candidate_set()["questions"][0].items() if key != "sourceGrounding"}]),
        _candidate_set(
            question_count=1,
            questions=[
                {
                    **_candidate_set()["questions"][0],
                    "options": [
                        {"optionLabel": "A", "optionText": "Queue", "sortOrder": 1, "isCorrect": True},
                        {"optionLabel": "B", "optionText": "Stack", "sortOrder": 2, "isCorrect": True},
                    ],
                }
            ],
        ),
    ],
)
def test_accept_rejects_invalid_ai_candidate_set_without_partial_write(candidate_set: dict) -> None:
    quiz = _quiz()
    old_question = _question()
    service, session = _service(quiz=quiz, existing_questions=[old_question])

    with pytest.raises(HTTPException) as exc_info:
        service.accept_educator_ai_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=EducatorQuizDraftAcceptRequest(candidateSet=candidate_set),
            current_user={"id": 7, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 502
    assert service.questions.created == []
    assert old_question.is_active is True
    assert session.commits == 0


def test_preview_permission_failure_short_circuits_ai_call() -> None:
    service, session = _service(quiz=_quiz(), existing_questions=[_question()])

    def deny_course(**_):
        raise HTTPException(status_code=404, detail="not found")

    service._get_manageable_course = deny_course

    with pytest.raises(HTTPException) as exc_info:
        service.preview_educator_ai_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=EducatorQuizDraftGenerateRequest(questionCount=1),
            current_user={"id": 9, "identity": "Educator"},
        )

    assert exc_info.value.status_code == 404
    assert service.educator_quiz_draft_ai.calls == []
    assert session.commits == 0


class FakeAPIQuizService:
    calls: list[dict] = []

    def __init__(self, session) -> None:
        self.session = session

    def generate_educator_ai_draft(self, **kwargs):
        self.calls.append({"method": "preview", **kwargs})
        current_user = kwargs["current_user"]
        if current_user.get("id") not in {7, 9}:
            raise HTTPException(status_code=404, detail={"code": "COURSE_NOT_FOUND", "message": "Course not found"})
        return {
            "title": "Generated Graph Quiz",
            "questionCount": 1,
            "difficulty": "mixed",
            "questionTypes": ["multiple_choice"],
            "replaceExistingQuestions": True,
            "timeLimitSeconds": None,
            "shuffleQuestions": True,
            "shuffleOptions": False,
            "retrievalUsed": True,
            "sourceChunkCount": 1,
            "candidateSet": _candidate_set(question_count=1, questions=[_candidate_set()["questions"][0]]),
        }

    def accept_educator_ai_draft(self, **kwargs):
        self.calls.append({"method": "accept", **kwargs})
        current_user = kwargs["current_user"]
        if current_user.get("id") not in {7, 9}:
            raise HTTPException(status_code=404, detail={"code": "COURSE_NOT_FOUND", "message": "Course not found"})
        return {
            "quizId": 3,
            "quizUuid": "quiz-uuid",
            "moduleId": 2,
            "moduleUuid": kwargs["module_uuid"],
            "title": "Generated Graph Quiz",
            "description": None,
            "status": "draft",
            "timeLimitSeconds": None,
            "questionCountPerAttempt": 1,
            "availableQuestionCount": 1,
            "shuffleQuestions": True,
            "shuffleOptions": False,
            "passingRule": "all_questions_correct",
            "publishedAt": None,
            "createdAt": datetime(2026, 6, 30, 12, 0, 0),
            "updatedAt": datetime(2026, 6, 30, 12, 0, 0),
            "questions": [],
        }


def _install_identity_payload(monkeypatch, *, token_user: dict[str, dict]) -> None:
    def fake_fetch_identity_payload(*, identity_service_url: str, token: str, path: str) -> dict:
        user = token_user[token]
        if path == "/auth/me":
            return {"id": user["id"], "identity": user["identity"]}
        if path == "/auth/me/permissions":
            permission_codes = user.get("permissions", [])
            return {"permissions": [{"permissionCode": code} for code in permission_codes]}
        raise AssertionError(f"Unexpected identity path: {path}")

    monkeypatch.setattr("platform_common.auth.dependencies.fetch_identity_payload", fake_fetch_identity_payload)


def _install_api_test_service(monkeypatch) -> None:
    FakeAPIQuizService.calls = []
    monkeypatch.setattr(quiz_api, "QuizService", FakeAPIQuizService)


def _current_user_dependency_for(path: str):
    for route in quiz_api.router.routes:
        if getattr(route, "path", None) == path:
            for dependency in route.dependant.dependencies:
                if dependency.name == "current_user":
                    return dependency.call
    raise AssertionError(f"current_user dependency not found for {path}")


def _assert_route_requires_module_update(path: str) -> None:
    dependency = _current_user_dependency_for(path)
    closure = inspect.getclosurevars(dependency)
    assert closure.nonlocals["permission_code"] == MODULE_UPDATE


def test_preview_endpoint_allows_owner_and_admin(monkeypatch) -> None:
    _install_api_test_service(monkeypatch)
    for current_user in ({"id": 7, "identity": "Educator"}, {"id": 9, "identity": "Admin"}):
        response = quiz_api.generate_ai_quiz_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=EducatorQuizDraftGenerateRequest(questionCount=1, questionTypes=["multiple_choice"]),
            current_user=current_user,
            session=object(),
        )

        assert response["candidateSet"]["questions"][0]["sourceGrounding"] == "Graphs notes, BFS section."

    assert [call["current_user"]["id"] for call in FakeAPIQuizService.calls] == [7, 9]


def test_accept_endpoint_allows_owner_and_admin(monkeypatch) -> None:
    _install_api_test_service(monkeypatch)

    for current_user in ({"id": 7, "identity": "Educator"}, {"id": 9, "identity": "Admin"}):
        response = quiz_api.accept_ai_quiz_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=EducatorQuizDraftAcceptRequest(
                candidateSet=_candidate_set(question_count=1, questions=[_candidate_set()["questions"][0]])
            ),
            current_user=current_user,
            session=object(),
        )

        assert response["status"] == "draft"

    assert [call["current_user"]["id"] for call in FakeAPIQuizService.calls] == [7, 9]
    assert all(call["method"] == "accept" for call in FakeAPIQuizService.calls)


def test_preview_endpoint_denies_non_owner_after_permission_dependency(monkeypatch) -> None:
    _install_api_test_service(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        quiz_api.generate_ai_quiz_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=EducatorQuizDraftGenerateRequest(questionCount=1, questionTypes=["multiple_choice"]),
            current_user={"id": 8, "identity": "Educator"},
            session=object(),
        )

    assert exc_info.value.status_code == 404
    assert FakeAPIQuizService.calls[0]["current_user"]["id"] == 8


def test_accept_endpoint_denies_non_owner_after_permission_dependency(monkeypatch) -> None:
    _install_api_test_service(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        quiz_api.accept_ai_quiz_draft(
            course_uuid="course-uuid",
            module_uuid="module-uuid",
            payload=EducatorQuizDraftAcceptRequest(
                candidateSet=_candidate_set(question_count=1, questions=[_candidate_set()["questions"][0]])
            ),
            current_user={"id": 8, "identity": "Educator"},
            session=object(),
        )

    assert exc_info.value.status_code == 404
    assert FakeAPIQuizService.calls[0]["method"] == "accept"
    assert FakeAPIQuizService.calls[0]["current_user"]["id"] == 8


def test_ai_draft_endpoints_reject_user_without_module_update(monkeypatch) -> None:
    FakeAPIQuizService.calls = []
    _install_identity_payload(
        monkeypatch,
        token_user={"learner-token": {"id": 10, "identity": "Learner", "permissions": []}},
    )
    paths = [
        "/courses/{course_uuid}/modules/{module_uuid}/quiz/management/ai-draft",
        "/courses/{course_uuid}/modules/{module_uuid}/quiz/management/ai-draft/accept",
    ]

    for path in paths:
        _assert_route_requires_module_update(path)
        dependency = _current_user_dependency_for(path)
        with pytest.raises(HTTPException) as exc_info:
            dependency("Bearer learner-token")

        assert exc_info.value.status_code == 403
    assert FakeAPIQuizService.calls == []
