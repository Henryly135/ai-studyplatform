from __future__ import annotations

from app.services.orchestration.langgraph.quiz_generation_graph import QuizGenerationGraphRunner
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationAutoStartWorkflowState,
    QuizGenerationRequest,
)


def run_generation_workflow_node(
    *,
    state: QuizGenerationAutoStartWorkflowState,
    session,
) -> QuizGenerationAutoStartWorkflowState:
    request = state["request"]
    generation_request = QuizGenerationRequest(
        courseUuid=request.courseUuid,
        moduleUuid=request.moduleUuid,
        educatorId=request.actorId,
        learnerId=request.actorId,
        additionalInstructions=request.additionalInstructions,
    )
    generation_result = QuizGenerationGraphRunner(session=session).run(payload=generation_request)
    return {
        **state,
        "generationRequest": generation_request,
        "generationResult": generation_result,
    }
