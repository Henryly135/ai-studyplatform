from __future__ import annotations

from app.services.workflows.profile_update.schemas import ProfileUpdateWorkflowState
from app.services.workflows.profile_update.services.decision_service import ModuleProfileUpdateDecisionService


def decide_update_node(*, state: ProfileUpdateWorkflowState) -> ProfileUpdateWorkflowState:
    context = state["context"]
    decision = ModuleProfileUpdateDecisionService().generate_decision(
        context=context.model_dump(mode="json"),
        validation_feedback=state.get("validationFeedback", []),
    )
    return {
        **state,
        "decision": decision,
    }
