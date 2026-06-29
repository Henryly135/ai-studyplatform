from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import QuizGenerationWorkflowState
from app.services.workflows.quiz_generation.services.planning_service import QuizGenerationPlanningService


def plan_quiz_node(*, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
    request = state["request"]
    plan = QuizGenerationPlanningService().build_plan(
        request=request,
        context=state["context"],
        retrieval_context=state["retrievalContext"],
        profile_context=state.get("profileContext"),
    )
    return {
        **state,
        "plan": plan,
    }
