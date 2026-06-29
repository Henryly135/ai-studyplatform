from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import (
    QuizGeneratedAttemptStartResponse,
)


def test_auto_generated_attempt_endpoint(app, client, monkeypatch):
    # Tests public auto-generated quiz attempt endpoint returns a started attempt.
    from app.api.quiz_generation import require_quiz_attempt_permission
    from app.services.orchestration.langgraph.generated_quiz_attempt_graph import GeneratedQuizAttemptGraphRunner
    from app.services.workflows.quiz_generation.services.learning_quiz_generation_client import LearningQuizGenerationClient

    app.dependency_overrides[require_quiz_attempt_permission] = lambda: {
        "id": 77,
        "identity": "Learner",
        "permissions": ["quiz.attempt"],
    }
    monkeypatch.setattr(
        LearningQuizGenerationClient,
        "ensure_learner_quiz_access",
        lambda self, course_uuid, module_uuid, learner_id: None,
    )
    monkeypatch.setattr(
        GeneratedQuizAttemptGraphRunner,
        "run",
        lambda self, payload, config=None: QuizGeneratedAttemptStartResponse(
            quizId=33,
            quizUuid="quiz-uuid",
            moduleId=22,
            moduleUuid="module-uuid",
            attemptSessionToken="token-123",
            attemptNumber=1,
            questionCount=2,
            timeLimitSeconds=600,
            startedAt="2026-01-01T00:00:00Z",
            expiresAt="2026-01-01T00:10:00Z",
            questions=[
                {
                    "questionId": 1001,
                    "questionUuid": "qq-1",
                    "questionText": "Which statement is correct?",
                    "explanationText": "Because ownership matters",
                    "questionOrder": 1,
                    "options": [
                        {
                            "optionId": 2001,
                            "optionUuid": "qo-1",
                            "optionLabel": "A",
                            "optionText": "Correct",
                            "sortOrder": 1,
                        }
                    ],
                }
            ],
        ),
    )

    response = client.post(
        "/courses/course-uuid/modules/module-uuid/quiz/generated-attempt-sessions/auto",
        json={"additionalInstructions": "Focus on ownership."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["attemptSessionToken"] == "token-123"
    assert body["questionCount"] == 2
