from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.short_answer import ShortAnswerEvaluationRequest, ShortAnswerEvaluationResponse


class ShortAnswerEvaluationService:
    """Deterministic evaluator for short-answer MVP; provider-backed generation can replace this service later."""

    def evaluate(self, payload: ShortAnswerEvaluationRequest) -> ShortAnswerEvaluationResponse:
        answer_words = self._words(payload.answerText)
        rubric_words = self._rubric_keywords(payload.rubricText)
        matched_keywords = sorted(set(answer_words) & rubric_words)
        coverage_ratio = Decimal(len(matched_keywords)) / Decimal(max(1, len(rubric_words)))
        length_ratio = min(Decimal(len(answer_words)) / Decimal("80"), Decimal("1.0"))
        score_ratio = min(Decimal("1.0"), Decimal("0.35") + coverage_ratio * Decimal("0.45") + length_ratio * Decimal("0.20"))
        score = (payload.maxScore * score_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        strengths = []
        if matched_keywords:
            strengths.append(f"Addresses key rubric ideas: {', '.join(matched_keywords[:4])}.")
        if len(answer_words) >= 40:
            strengths.append("Provides enough detail for a substantive short answer.")
        if not strengths:
            strengths.append("Provides a direct response to the prompt.")

        improvements = []
        if len(answer_words) < 40:
            improvements.append("Add more explanation and evidence from the module materials.")
        missing = sorted(rubric_words - set(answer_words))
        if missing:
            improvements.append(f"Connect the answer more clearly to: {', '.join(missing[:4])}.")
        if not improvements:
            improvements.append("Tighten the explanation by explicitly linking claims to the rubric.")

        feedback = (
            f"Suggested score {score}/{payload.maxScore}. "
            "The response has been checked against the rubric and should be reviewed by the educator before final release."
        )
        return ShortAnswerEvaluationResponse(
            scoreSuggestion=score,
            feedbackText=feedback,
            strengths=strengths[:5],
            improvements=improvements[:5],
            provider="local",
            model="short-answer-rubric-heuristic-v1",
        )

    def _words(self, text: str) -> list[str]:
        return [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)]

    def _rubric_keywords(self, text: str) -> set[str]:
        words = set(self._words(text))
        stop_words = {
            "and",
            "the",
            "for",
            "with",
            "that",
            "this",
            "from",
            "should",
            "must",
            "answer",
            "explain",
            "include",
            "describe",
            "student",
            "students",
        }
        return {word for word in words if word not in stop_words}
