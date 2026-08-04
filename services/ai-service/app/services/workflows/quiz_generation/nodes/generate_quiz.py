from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationWorkflowState
from app.services.workflows.quiz_generation.services.generation_service import QuizCandidateGenerationService


def generate_quiz_node(*, state: QuizGenerationWorkflowState, session=None) -> QuizGenerationWorkflowState:
    request = state["request"]
    candidate_set = QuizCandidateGenerationService(session=session).generate_candidates(
        request=request,
        context=state["context"],
        retrieval_context=state["retrievalContext"],
        plan=state["plan"],
        profile_context=state.get("profileContext"),
    )
    return {
        **state,
        "candidateSet": candidate_set,
    }
