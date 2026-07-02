from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationCandidateQuestion, QuizGenerationCandidateSetRead
from platform_common.errors import invalid_request_error


class QuizGenerationValidationService:
    def validate_candidate_set(
        self,
        *,
        candidate_set: QuizGenerationCandidateSetRead,
        required_question_count: int,
    ) -> QuizGenerationCandidateSetRead:
        if candidate_set.questionCount != required_question_count:
            raise invalid_request_error("Generated question count does not match the quiz configuration")
        if len(candidate_set.questions) != required_question_count:
            raise invalid_request_error("Generated question list does not match the quiz configuration")

        normalized_questions = [
            self._normalize_question(question=question)
            for question in candidate_set.questions
        ]
        return QuizGenerationCandidateSetRead(
            questionCount=required_question_count,
            questions=normalized_questions,
        )

    def _normalize_question(self, *, question: QuizGenerationCandidateQuestion) -> QuizGenerationCandidateQuestion:
        normalized_options = []
        for index, option in enumerate(question.options, start=1):
            label = option.optionLabel
            if label is None and len(question.options) <= 4:
                label = chr(ord("A") + index - 1)
            normalized_options.append(
                {
                    "optionLabel": label,
                    "optionText": option.optionText.strip(),
                    "sortOrder": index,
                    "isCorrect": option.isCorrect,
                }
            )

        return QuizGenerationCandidateQuestion.model_validate(
            {
                "questionText": question.questionText.strip(),
                "explanationText": question.explanationText.strip() if question.explanationText else None,
                "sortOrder": question.sortOrder,
                "isActive": True,
                "options": normalized_options,
            }
        )
