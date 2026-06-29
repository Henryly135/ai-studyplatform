from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationWorkflowState
from app.services.workflows.quiz_generation.services.load_inputs_service import QuizGenerationInputService


def load_inputs_node(*, state: QuizGenerationWorkflowState, session=None) -> QuizGenerationWorkflowState:
    request = state["request"]
    input_service = QuizGenerationInputService(session=session)
    context = input_service.load_context(payload=request)
    profile_context = input_service.load_profile_context(payload=request)
    return {
        **state,
        "context": context,
        "profileContext": profile_context,
    }
