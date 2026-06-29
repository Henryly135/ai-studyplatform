from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationAutoStartWorkflowState
from app.services.workflows.quiz_generation.services.learning_quiz_generation_client import LearningQuizGenerationClient


def start_generated_attempt_node(
    *,
    state: QuizGenerationAutoStartWorkflowState,
) -> QuizGenerationAutoStartWorkflowState:
    request = state["request"]
    generation_result = state["generationResult"]
    question_uuids = [question.questionUuid for question in generation_result.createdQuestions]
    attempt_start_response = LearningQuizGenerationClient().start_generated_attempt_internal(
        course_uuid=request.courseUuid,
        module_uuid=request.moduleUuid,
        learner_id=request.actorId,
        question_uuids=question_uuids,
    )
    return {
        **state,
        "attemptStartResponse": attempt_start_response,
    }
