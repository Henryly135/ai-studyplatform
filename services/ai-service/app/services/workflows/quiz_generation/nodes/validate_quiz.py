from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationWorkflowState
from app.services.workflows.quiz_generation.services.validation_service import QuizGenerationValidationService


def validate_quiz_node(*, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
    context = state["context"]
    candidate_set = QuizGenerationValidationService().validate_candidate_set(
        candidate_set=state["candidateSet"],
        required_question_count=context.questionCountPerAttempt,
    )
    return {
        **state,
        "candidateSet": candidate_set,
    }
