from __future__ import annotations

from app.services.workflows.profile_update.schemas import ProfileUpdateWorkflowState
from app.services.workflows.profile_update.services.candidate_service import ModuleProfileCandidateService


def submit_candidate_node(*, state: ProfileUpdateWorkflowState, session) -> ProfileUpdateWorkflowState:
    request = state["request"]
    decision = state["decision"]
    candidate_service = ModuleProfileCandidateService(session)
    candidate_request = candidate_service.build_candidate_request(
        learner_id=request.learnerId,
        course_uuid=request.courseUuid,
        module_uuid=request.moduleUuid,
        source=request.triggerSource,
        update_mode=decision.update_mode or "light_update",
        reason=decision.reason,
        patch=decision.patch,
    )
    candidate_result = candidate_service.submit_candidate_patch(payload=candidate_request)
    return {
        **state,
        "candidateRequest": candidate_request,
        "candidateResult": candidate_result,
        "attemptCount": state.get("attemptCount", 0) + 1,
    }
