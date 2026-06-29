from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.services.workflows.quiz_generation.nodes.run_generation_workflow import run_generation_workflow_node
from app.services.workflows.quiz_generation.nodes.start_generated_attempt import start_generated_attempt_node
from app.services.workflows.quiz_generation.schemas import (
    QuizGeneratedAttemptStartResponse,
    QuizGenerationAutoStartRunRequest,
    QuizGenerationAutoStartWorkflowState,
)
from platform_common.errors import invalid_request_error


logger = logging.getLogger(__name__)


class GeneratedQuizAttemptGraphRunner:
    def __init__(self, session, checkpointer=None) -> None:
        self.session = session
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def run(
        self,
        *,
        payload: QuizGenerationAutoStartRunRequest,
        config: dict | None = None,
    ) -> QuizGeneratedAttemptStartResponse:
        logger.info(
            "Starting generated quiz attempt graph",
            extra={
                "actorId": payload.actorId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
            },
        )
        state: QuizGenerationAutoStartWorkflowState = {"request": payload}
        final_state = self.graph.invoke(state, config=config)
        result = final_state.get("attemptStartResponse")
        if result is None:
            raise invalid_request_error("Generated quiz attempt graph did not produce an attempt start response")
        logger.info(
            "Completed generated quiz attempt graph",
            extra={
                "actorId": payload.actorId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
                "questionCount": result.questionCount,
                "attemptNumber": result.attemptNumber,
            },
        )
        return result

    def _build_graph(self):
        graph = StateGraph(QuizGenerationAutoStartWorkflowState)
        graph.add_node("run_generation_workflow", self._run_generation_workflow)
        graph.add_node("start_generated_attempt", self._start_generated_attempt)

        graph.add_edge(START, "run_generation_workflow")
        graph.add_edge("run_generation_workflow", "start_generated_attempt")
        graph.add_edge("start_generated_attempt", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _run_generation_workflow(
        self,
        state: QuizGenerationAutoStartWorkflowState,
    ) -> QuizGenerationAutoStartWorkflowState:
        return run_generation_workflow_node(state=state, session=self.session)

    def _start_generated_attempt(
        self,
        state: QuizGenerationAutoStartWorkflowState,
    ) -> QuizGenerationAutoStartWorkflowState:
        return start_generated_attempt_node(state=state)
