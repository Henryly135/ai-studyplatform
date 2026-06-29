from __future__ import annotations

from decimal import Decimal

from app.schemas.short_answer import ShortAnswerEvaluationRequest, ShortAnswerEvaluationResponse
from app.services.short_answer_evaluation_service import ShortAnswerEvaluationService


def _payload() -> dict:
    return {
        "assessmentUuid": "assessment-uuid",
        "title": "Explain BFS",
        "promptText": "Explain how BFS explores a graph.",
        "rubricText": "Mentions queue, levels, visited nodes, and traversal order.",
        "maxScore": "10.00",
        "answerText": "BFS uses a queue and visits nodes level by level while tracking visited nodes.",
    }


def test_short_answer_evaluation_service_returns_bounded_suggestion() -> None:
    response = ShortAnswerEvaluationService().evaluate(payload=ShortAnswerEvaluationRequest(**_payload()))

    assert Decimal("0.00") <= response.scoreSuggestion <= Decimal("10.00")
    assert response.feedbackText
    assert response.strengths
    assert response.improvements


def test_internal_short_answer_endpoint_success(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ShortAnswerEvaluationService,
        "evaluate",
        lambda self, payload: ShortAnswerEvaluationResponse(
            scoreSuggestion=Decimal("9.00"),
            feedbackText="Strong rubric coverage.",
            strengths=["Uses evidence."],
            improvements=["Name one limitation."],
            provider="test",
            model="stub",
        ),
    )

    response = client.post("/internal/short-answer/evaluate", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["scoreSuggestion"] == "9.00"
    assert body["strengths"] == ["Uses evidence."]


def test_internal_short_answer_endpoint_rejects_blank_answer(client) -> None:
    payload = {**_payload(), "answerText": "   "}

    response = client.post("/internal/short-answer/evaluate", json=payload)

    assert response.status_code == 422
