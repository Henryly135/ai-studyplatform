from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationWorkflowState
from app.services.workflows.quiz_generation.services.retrieval_service import QuizGenerationRetrievalService


def retrieve_context_node(*, state: QuizGenerationWorkflowState, session) -> QuizGenerationWorkflowState:
    request = state["request"]
    context = state["context"]
    retrieval_context = QuizGenerationRetrievalService(session).load_context(
        educator_id=request.educatorId,
        course_uuid=request.courseUuid,
        module_uuid=request.moduleUuid,
        quiz_title=context.quizTitle,
        module_title=context.moduleTitle,
        question_count=context.questionCountPerAttempt,
        additional_instructions=request.additionalInstructions,
    )
    return {
        **state,
        "retrievalContext": retrieval_context,
    }
