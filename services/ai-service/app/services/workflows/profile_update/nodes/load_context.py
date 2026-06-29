from __future__ import annotations

from app.services.workflows.profile_update.schemas import ProfileUpdateWorkflowState
from app.services.workflows.profile_update.services.context_service import ModuleUpdateContextService


def load_context_node(*, state: ProfileUpdateWorkflowState, session) -> ProfileUpdateWorkflowState:
    request = state["request"]
    context = ModuleUpdateContextService(session).build_context(payload=request)
    return {
        **state,
        "context": context,
    }
