from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationWorkflowState
from app.services.workflows.quiz_generation.services.publishing_service import QuizGenerationPublishingService


def publish_quiz_node(*, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
    request = state["request"]
    created_questions = QuizGenerationPublishingService().publish_generated_questions(
        course_uuid=request.courseUuid,
        module_uuid=request.moduleUuid,
        candidate_set=state["candidateSet"],
        purpose="attempt" if request.learnerId is not None else "authoring",
    )
    return {
        **state,
        "createdQuestions": created_questions,
    }
