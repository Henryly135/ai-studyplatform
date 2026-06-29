from __future__ import annotations

from app.services.workflows.profile_update.schemas import (
    ModuleProfileUpdateCheckDecision,
    ModuleProfileUpdateCheckResponse,
    ProfileUpdateWorkflowState,
)


def finalize_result_node(*, state: ProfileUpdateWorkflowState) -> ModuleProfileUpdateCheckResponse:
    decision = state["decision"]
    if not decision.should_update:
        return ModuleProfileUpdateCheckResponse(
            decision=ModuleProfileUpdateCheckDecision(
                should_update=False,
                update_mode=None,
                reason=decision.reason,
                patch={},
            ),
            candidateResult=None,
        )
    return ModuleProfileUpdateCheckResponse(
        decision=decision,
        candidateResult=state.get("candidateResult"),
    )
