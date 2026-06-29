from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.services.workflows.quiz_generation.nodes.generate_quiz import generate_quiz_node
from app.services.workflows.quiz_generation.nodes.load_inputs import load_inputs_node
from app.services.workflows.quiz_generation.nodes.plan_quiz import plan_quiz_node
from app.services.workflows.quiz_generation.nodes.publish_quiz import publish_quiz_node
from app.services.workflows.quiz_generation.nodes.retrieve_context import retrieve_context_node
from app.services.workflows.quiz_generation.nodes.validate_quiz import validate_quiz_node
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationRequest,
    QuizGenerationRunResponse,
    QuizGenerationWorkflowState,
)


logger = logging.getLogger(__name__)


class QuizGenerationGraphRunner:
    def __init__(self, session, checkpointer=None) -> None:
        self.session = session
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def run(self, *, payload: QuizGenerationRequest, config: dict | None = None) -> QuizGenerationRunResponse:
        logger.info(
            "Starting quiz generation workflow",
            extra={
                "educatorId": payload.educatorId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
            },
        )
        state: QuizGenerationWorkflowState = {"request": payload}
        final_state = self.graph.invoke(state, config=config)
        result = QuizGenerationRunResponse(
            context=final_state["context"],
            profileContext=final_state.get("profileContext"),
            retrievalContext=final_state["retrievalContext"],
            plan=final_state["plan"],
            candidateSet=final_state["candidateSet"],
            createdQuestions=final_state["createdQuestions"],
        )
        logger.info(
            "Completed quiz generation workflow",
            extra={
                "educatorId": payload.educatorId,
                "courseUuid": payload.courseUuid,
                "moduleUuid": payload.moduleUuid,
                "createdQuestionCount": len(result.createdQuestions),
            },
        )
        return result

    def _build_graph(self):
        graph = StateGraph(QuizGenerationWorkflowState)
        graph.add_node("load_inputs", self._load_inputs)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("plan_quiz", self._plan_quiz)
        graph.add_node("generate_quiz", self._generate_quiz)
        graph.add_node("validate_quiz", self._validate_quiz)
        graph.add_node("publish_quiz", self._publish_quiz)

        graph.add_edge(START, "load_inputs")
        graph.add_edge("load_inputs", "retrieve_context")
        graph.add_edge("retrieve_context", "plan_quiz")
        graph.add_edge("plan_quiz", "generate_quiz")
        graph.add_edge("generate_quiz", "validate_quiz")
        graph.add_edge("validate_quiz", "publish_quiz")
        graph.add_edge("publish_quiz", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _load_inputs(self, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
        return load_inputs_node(state=state, session=self.session)

    def _retrieve_context(self, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
        return retrieve_context_node(state=state, session=self.session)

    def _plan_quiz(self, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
        return plan_quiz_node(state=state)

    def _generate_quiz(self, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
        return generate_quiz_node(state=state)

    def _validate_quiz(self, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
        return validate_quiz_node(state=state)

    def _publish_quiz(self, state: QuizGenerationWorkflowState) -> QuizGenerationWorkflowState:
        return publish_quiz_node(state=state)
